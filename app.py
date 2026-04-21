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
# PAGE SETUP
# --------------------------------------------------
st.set_page_config(page_title="APHC Ultimate Matcher", layout="wide")
st.title("⚖️ APHC Ultimate Case Matcher")

# --------------------------------------------------
# EXTRACT CASES (STRICT RULES)
# --------------------------------------------------
def extract_cases(text):
    text = re.sub(r"\([^)]*\)", "", text)

    lines = text.splitlines()
    lines = [l for l in lines if "ARISING FROM" not in l.upper()]
    text = " ".join(lines)

    text = re.sub(r"\s+", " ", text)

    matches = re.findall(r"WP\s*/\s*\d+\s*/\s*\d+", text, re.I)

    clean = []
    for m in matches:
        m = re.sub(r"\s*/\s*", "/", m)
        parts = m.upper().split("/")
        try:
            clean.append(f"WP/{int(parts[1])}/{int(parts[2])}")
        except:
            continue

    return sorted(set(clean))

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
        except:
            st.warning(f"⚠️ Failed to read: {url}")
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
        st.success("PDF processed")

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
            st.warning(f"⚠️ Sheet '{sheet}' skipped: No case column")
            continue

        # -------------------------
        # CASE CLEANING
        # -------------------------
        df[case_col] = df[case_col].astype(str)
        df[case_col] = df[case_col].str.replace(r"\D", "", regex=True)
        df = df[df[case_col] != ""]

        if df.empty:
            continue

        # -------------------------
        # YEAR LOGIC (ROW SAFE)
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

            try:
                case_num = int(case_val)
                year_num = int(year_val)

                full_case = f"WP/{case_num}/{year_num}"

                valid_indices.append(idx)
                full_cases.append(full_case)

            except:
                skipped_rows.append({
                    "Sheet": sheet,
                    "Row_Index": idx,
                    "Case_No": case_val,
                    "Year": year_val,
                    "Reason": "Invalid case/year"
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

    # --------------------------------------------------
    # OUTPUT
    # --------------------------------------------------
    if results:
        final = pd.concat(results, ignore_index=True)
        final.drop(columns=["__fullcase", "__year"], inplace=True, errors="ignore")

        st.success(f"✅ Matched: {len(final)}")
        st.dataframe(final)

    else:
        st.warning("No matches found")

    # -------------------------
    # UNMATCHED SUMMARY
    # -------------------------
    unmatched = main_cases - matched_cases
    st.write(f"❌ Unmatched Cases: {len(unmatched)}")
    st.write(list(unmatched)[:20])

    # -------------------------
    # SKIPPED ROWS DISPLAY
    # -------------------------
    if skipped_rows:
        st.warning(f"⚠️ Skipped Rows: {len(skipped_rows)}")
        skipped_df = pd.DataFrame(skipped_rows)
        st.dataframe(skipped_df)

    # -------------------------
    # EXCEL DOWNLOAD (HIGHLIGHT)
    # -------------------------
    output = BytesIO()

    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        final.to_excel(writer, index=False, sheet_name="Matched")

        workbook = writer.book
        worksheet = writer.sheets["Matched"]

        green = workbook.add_format({"bg_color": "#C6EFCE"})

        for row in range(1, len(final) + 1):
            worksheet.set_row(row, cell_format=green)

        pd.DataFrame({"Unmatched": list(unmatched)}).to_excel(
            writer, sheet_name="Unmatched", index=False
        )

        if skipped_rows:
            pd.DataFrame(skipped_rows).to_excel(
                writer, sheet_name="Skipped Rows", index=False
            )

    st.download_button(
        "📥 Download Excel (Formatted)",
        output.getvalue(),
        "final_output.xlsx"
    )

else:
    st.info("Provide input and Excel")
