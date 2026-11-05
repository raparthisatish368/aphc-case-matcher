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
# EXTRACT CASES
# --------------------------------------------------
def extract_cases(text):
    # Match special case types first so WP(AT) is not mistaken for WP.
    case_pattern = re.compile(
        r"\b(WP\s*\(\s*AT\s*\)|CC\s*\(\s*AT\s*\)|WP|CC)"
        r"\s*/?\s*(\d+)\s*/\s*(\d{4})\b",
        re.IGNORECASE
    )

    cases = set()
    skip_related_case = False

    for line in text.splitlines():

        # Ignore the case mentioned under "ARISING FROM".
        if "ARISING FROM" in line.upper():
            skip_related_case = True
            continue

        matches = list(case_pattern.finditer(line))

        if not matches:
            continue

        if skip_related_case:
            # Ignore the first case number following "ARISING FROM".
            skip_related_case = False
            continue

        for match in matches:
            case_type = re.sub(r"\s+", "", match.group(1).upper())
            case_no = int(match.group(2))
            year = int(match.group(3))

            cases.add(f"{case_type}/{case_no}/{year}")

    return sorted(cases)

# --------------------------------------------------
# PDF READER
# --------------------------------------------------
def read_pdfs(urls):
    text = ""
    for url in urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=20, verify=False)
            r.raise_for_status()
            with pdfplumber.open(BytesIO(r.content)) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        text += t + "\n"
        except Exception as e:
            st.warning(f"⚠️ Failed: {url}")
            st.code(repr(e))

    return text

# --------------------------------------------------
# INPUT
# --------------------------------------------------
mode = st.radio("Input Mode", ["PDF Links", "Manual Text"])

cause_text = ""

if mode == "PDF Links":
    links = st.text_area("Paste PDF links (one per line)")
    if st.button("Read PDFs"):
        urls = [l.strip() for l in links.splitlines() if l.startswith("http")]
        cause_text = read_pdfs(urls)

        if cause_text.strip():
            st.success("PDF processed")
            st.session_state["cause_text"] = cause_text
        else:
            st.error("No text could be extracted from the PDF links.")

    cause_text = st.session_state.get("cause_text", "")

else:
    cause_text = st.text_area("Paste cause list text", height=300)

xls_file = st.file_uploader("Upload Excel", type=["xlsx", "xls"])

# --------------------------------------------------
# PROCESS
# --------------------------------------------------
if cause_text and xls_file:

    main_cases = set(extract_cases(cause_text))
    st.write(f"📊 Extracted Cases: {len(main_cases)}")

    xls = pd.ExcelFile(xls_file)

    results = []
    skipped_rows = []
    matched_cases = set()

    for sheet in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name=sheet)
        df.columns = [str(c).lower().strip() for c in df.columns]

        case_col = next((c for c in df.columns if "case" in c), None)
        year_col = next((c for c in df.columns if "year" in c), None)

        if not case_col:
            continue

        # -------------------------
        # DETECT CASE TYPE FROM SHEET NAME
        # -------------------------
        normalized_sheet = re.sub(r"\s+", "", str(sheet)).upper()

        if "WP(AT)" in normalized_sheet:
            sheet_case_type = "WP(AT)"
        elif "CC(AT)" in normalized_sheet:
            sheet_case_type = "CC(AT)"
        elif normalized_sheet.startswith("CC"):
            sheet_case_type = "CC"
        else:
            # Preserve existing behavior for ordinary year-wise sheets.
            sheet_case_type = "WP"

        # -------------------------
        # CLEAN CASE NO
        # -------------------------
        df[case_col] = pd.to_numeric(df[case_col], errors="coerce")
        df[case_col] = df[case_col].astype("Int64")

        df = df[df[case_col].notna()]

        if df.empty:
            continue

        # -------------------------
        # YEAR LOGIC
        # -------------------------
        detected_year = None
        year_series = None

        if year_col:
            year_series = pd.to_numeric(df[year_col], errors="coerce")
            if year_series.notna().any():
                detected_year = int(year_series.dropna().iloc[0])

        if not detected_year:
            m = re.search(r"(19|20)\d{2}", str(sheet))
            if m:
                detected_year = int(m.group())

        if year_series is not None:
            df["__year"] = year_series
        else:
            df["__year"] = None

        if detected_year:
            df["__year"] = df["__year"].fillna(detected_year)

        df["__year"] = pd.to_numeric(df["__year"], errors="coerce")

        # -------------------------
        # ROW VALIDATION
        # -------------------------
        valid_indices = []
        full_cases = []

        for idx, row in df.iterrows():

            case_val = row[case_col]
            year_val = row["__year"]

            if pd.isna(year_val):
                year_val = detected_year

            try:
                case_num = int(case_val)

                if pd.isna(year_val):
                    raise ValueError

                year_num = int(year_val)

                # Use the case type detected from the sheet name.
                full_case = f"{sheet_case_type}/{case_num}/{year_num}"

                valid_indices.append(idx)
                full_cases.append(full_case)

            except Exception:
                skipped_rows.append({
                    "Sheet": sheet,
                    "Row_Index": idx,
                    "Case_No": case_val,
                    "Year": year_val,
                    "Reason": "Invalid case or year"
                })

        df = df.loc[valid_indices]
        df["__fullcase"] = full_cases

        # -------------------------
        # MATCHING
        # -------------------------
        hit = df[df["__fullcase"].isin(main_cases)].copy()

        if not hit.empty:
            hit["Sheet"] = sheet
            matched_cases.update(hit["__fullcase"])
            results.append(hit)

    # -------------------------
    # FINAL RESULT
    # -------------------------
    if results:
        final = pd.concat(results, ignore_index=True)
        final.drop(columns=["__fullcase", "__year"], inplace=True, errors="ignore")

        st.success(f"✅ Matched Rows: {len(final)}")
        st.dataframe(final)

    else:
        st.warning("No matches found")
        final = pd.DataFrame()

    # -------------------------
    # UNMATCHED
    # -------------------------
    unmatched = main_cases - matched_cases
    st.write(f"❌ Unmatched Cases: {len(unmatched)}")
    st.write(list(unmatched)[:20])

    # -------------------------
    # SKIPPED ROWS
    # -------------------------
    if skipped_rows:
        st.warning(f"⚠️ Skipped Rows: {len(skipped_rows)}")
        skipped_df = pd.DataFrame(skipped_rows)
        st.dataframe(skipped_df)

    # -------------------------
    # EXCEL DOWNLOAD
    # -------------------------
    output = BytesIO()

    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:

        if not final.empty:
            final.to_excel(writer, index=False, sheet_name="Matched")
        else:
            pd.DataFrame({"Message": ["No matched cases"]}).to_excel(
                writer, sheet_name="Matched", index=False
            )

        pd.DataFrame({"Unmatched": list(unmatched)}).to_excel(
            writer, index=False, sheet_name="Unmatched"
        )

        if skipped_rows:
            pd.DataFrame(skipped_rows).to_excel(
                writer, index=False, sheet_name="Skipped Rows"
            )

    st.download_button(
        "📥 Download Excel",
        output.getvalue(),
        "final_output.xlsx"
    )

else:
    st.info("Provide input and Excel")
