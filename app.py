import streamlit as st
import pandas as pd
import re
import requests
import pdfplumber
from io import BytesIO
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HEADERS = {"User-Agent": "APHC-Case-Matcher"}

# --------------------------------------------------
# PAGE
# --------------------------------------------------
st.set_page_config(page_title="APHC Case Matcher", layout="wide")
st.title("⚖️ APHC Case Matcher")


# --------------------------------------------------
# EXTRACT CASES FROM CAUSE LIST
# Supports WP/123/2025, (WP/123/2025), WP(AT)/123/2025,
# CC/123/2025 and CC(AT)/123/2025.
# Skips the WP reference associated with "ARISING FROM".
# --------------------------------------------------
def extract_cases(text):
    cases = set()
    skip_next_reference = False

    pattern = re.compile(
        r"\b(WP|CC)\s*(?:\(\s*AT\s*\))?\s*/\s*(\d+)\s*/\s*(\d+)",
        re.IGNORECASE
    )

    for line in text.splitlines():
        if "ARISING FROM" in line.upper():
            skip_next_reference = True

        matches = list(pattern.finditer(line))

        for match in matches:
            if skip_next_reference:
                skip_next_reference = False
                continue

            case_type = match.group(1).upper()
            case_number = int(match.group(2))
            case_year = int(match.group(3))

            cases.add(f"{case_type}/{case_number}/{case_year}")

    return sorted(cases)


# --------------------------------------------------
# PDF READER
# --------------------------------------------------
def read_pdfs(urls):
    text = ""

    for url in urls:
        try:
            response = requests.get(
                url,
                headers=HEADERS,
                timeout=30,
                verify=False
            )
            response.raise_for_status()

            with pdfplumber.open(BytesIO(response.content)) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"

        except Exception as e:
            st.error(f"Failed to read PDF: {url}")
            st.code(repr(e))

    return text


# --------------------------------------------------
# INPUT
# --------------------------------------------------
mode = st.radio("Input Mode", ["PDF Links", "Manual Text"])

if "cause_text" not in st.session_state:
    st.session_state.cause_text = ""

if mode == "PDF Links":
    links = st.text_area("Paste PDF links (one per line)")

    if st.button("Read PDFs"):
        urls = [
            line.strip()
            for line in links.splitlines()
            if line.strip().startswith("http")
        ]

        if not urls:
            st.warning("Please enter at least one valid PDF link.")
        else:
            st.session_state.cause_text = read_pdfs(urls)

            if st.session_state.cause_text.strip():
                st.success("PDF text extracted.")
            else:
                st.error("No text was extracted. Check the PDF link or try Manual Text.")

else:
    st.session_state.cause_text = st.text_area(
        "Paste cause list text",
        value=st.session_state.cause_text,
        height=300
    )

xls_file = st.file_uploader("Upload Excel", type=["xlsx", "xls"])


# --------------------------------------------------
# HELPERS
# --------------------------------------------------
def get_sheet_case_type(sheet_name):
    """
    Determine the case type from the sheet name.
    Examples:
      WP(AT) 2021 -> WP(AT)
      CC(AT) 2021 -> CC(AT)
      WP 2021     -> WP
      2021 new    -> WP (default)
    """
    name = str(sheet_name).upper().replace(" ", "")

    if "CC(AT)" in name:
        return "CC(AT)"
    if "WP(AT)" in name:
        return "WP(AT)"
    if "CC" in name:
        return "CC"

    return "WP"


def get_case_number(value):
    """Accept numeric Excel values such as 203 or 203.0."""
    if pd.isna(value):
        return None

    try:
        number = float(value)
        if number.is_integer():
            return int(number)
    except (TypeError, ValueError):
        pass

    return None


# --------------------------------------------------
# PROCESS
# --------------------------------------------------
cause_text = st.session_state.cause_text

if cause_text.strip() and xls_file:

    main_cases = set(extract_cases(cause_text))
    st.write(f"📊 Extracted Cases: {len(main_cases)}")

    try:
        xls = pd.ExcelFile(xls_file)
    except Exception as e:
        st.error("Could not open the Excel file.")
        st.code(repr(e))
        st.stop()

    results = []
    skipped_rows = []
    matched_cases = set()

    for sheet in xls.sheet_names:
        try:
            df = pd.read_excel(xls, sheet_name=sheet)
        except Exception as e:
            skipped_rows.append({
                "Sheet": sheet,
                "Row_Index": "",
                "Case_No": "",
                "Year": "",
                "Reason": f"Could not read sheet: {e}"
            })
            continue

        df.columns = [str(column).lower().strip() for column in df.columns]

        case_col = next(
            (column for column in df.columns if "case" in column),
            None
        )
        year_col = next(
            (column for column in df.columns if "year" in column),
            None
        )

        if not case_col:
            skipped_rows.append({
                "Sheet": sheet,
                "Row_Index": "",
                "Case_No": "",
                "Year": "",
                "Reason": "No Case No. column found"
            })
            continue

        case_type = get_sheet_case_type(sheet)

        # --------------------------------------------------
        # CLEAN NUMERIC CASE NUMBERS
        # --------------------------------------------------
        raw_case_values = df[case_col].copy()
        df[case_col] = raw_case_values.apply(get_case_number)

        invalid_case_mask = (
            raw_case_values.notna() &
            df[case_col].isna()
        )

        for idx in df.index[invalid_case_mask]:
            skipped_rows.append({
                "Sheet": sheet,
                "Row_Index": idx,
                "Case_No": raw_case_values.loc[idx],
                "Year": df.loc[idx, year_col] if year_col else None,
                "Reason": "Case No. is not numeric"
            })

        df = df[df[case_col].notna()].copy()
        df[case_col] = df[case_col].astype("Int64")

        if df.empty:
            continue

        # --------------------------------------------------
        # YEAR LOGIC
        # --------------------------------------------------
        detected_year = None

        if year_col:
            year_series = pd.to_numeric(df[year_col], errors="coerce")

            if year_series.notna().any():
                detected_year = int(year_series.dropna().iloc[0])
        else:
            year_series = pd.Series(index=df.index, dtype="float64")

        if detected_year is None:
            year_match = re.search(r"(19|20)\d{2}", str(sheet))
            if year_match:
                detected_year = int(year_match.group())

        df["__year"] = year_series

        if detected_year is not None:
            df["__year"] = df["__year"].fillna(detected_year)

        # --------------------------------------------------
        # BUILD FULL CASE NUMBERS
        # --------------------------------------------------
        valid_indices = []
        full_cases = []

        for idx, row in df.iterrows():
            case_value = row[case_col]
            year_value = row["__year"]

            try:
                if pd.isna(year_value):
                    raise ValueError("Missing case year")

                case_number = int(case_value)
                case_year = int(year_value)

                full_case = f"{case_type}/{case_number}/{case_year}"

                valid_indices.append(idx)
                full_cases.append(full_case)

            except (ValueError, TypeError, OverflowError):
                skipped_rows.append({
                    "Sheet": sheet,
                    "Row_Index": idx,
                    "Case_No": case_value,
                    "Year": year_value,
                    "Reason": "Invalid or missing case year"
                })

        df = df.loc[valid_indices].copy()
        df["__fullcase"] = full_cases

        # --------------------------------------------------
        # MATCH
        # --------------------------------------------------
        hit = df[df["__fullcase"].isin(main_cases)].copy()

        if not hit.empty:
            hit["Sheet"] = sheet
            matched_cases.update(hit["__fullcase"])
            results.append(hit)

    # --------------------------------------------------
    # DISPLAY MATCHED RESULTS
    # --------------------------------------------------
    if results:
        final = pd.concat(results, ignore_index=True)
        final.drop(
            columns=["__fullcase", "__year"],
            inplace=True,
            errors="ignore"
        )

        st.success(f"✅ Matched Rows: {len(final)}")
        st.dataframe(final, use_container_width=True)

    else:
        st.warning("No matches found.")
        final = pd.DataFrame()

    # --------------------------------------------------
    # UNMATCHED CASES
    # --------------------------------------------------
    unmatched = main_cases - matched_cases

    st.write(f"❌ Unmatched Cases: {len(unmatched)}")

    if unmatched:
        st.write(sorted(unmatched)[:50])

    # --------------------------------------------------
    # SKIPPED ROWS
    # --------------------------------------------------
    skipped_df = pd.DataFrame(skipped_rows)

    if not skipped_df.empty:
        st.warning(f"⚠️ Skipped Rows: {len(skipped_df)}")
        st.dataframe(skipped_df, use_container_width=True)

    # --------------------------------------------------
    # EXCEL DOWNLOAD
    # --------------------------------------------------
    output = BytesIO()

    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:

        if not final.empty:
            final.to_excel(writer, index=False, sheet_name="Matched")
        else:
            pd.DataFrame(
                {"Message": ["No matched cases"]}
            ).to_excel(writer, index=False, sheet_name="Matched")

        pd.DataFrame(
            {"Unmatched": sorted(unmatched)}
        ).to_excel(writer, index=False, sheet_name="Unmatched")

        if not skipped_df.empty:
            skipped_df.to_excel(
                writer,
                index=False,
                sheet_name="Skipped Rows"
            )

    st.download_button(
        "📥 Download Excel",
        data=output.getvalue(),
        file_name="final_output.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

else:
    st.info("Provide cause list input and upload an Excel file.")
