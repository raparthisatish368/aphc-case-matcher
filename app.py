import streamlit as st
import pandas as pd
import re
import requests
from bs4 import BeautifulSoup
import pdfplumber
import io

# --------------------------------------------------
# Page configuration
# --------------------------------------------------
st.set_page_config(
    page_title="APHC Case Matcher – Auto / Manual",
    page_icon="⚖️",
    layout="wide"
)

st.title("⚖️ APHC Case Matcher (Manual or Automatic Cause List)")

st.markdown("""
### How this app works
- Choose **Cause List source**:
  - ✍️ Manual paste **OR**
  - 🤖 Automatic fetch from APHC Online Board
- Upload **Excel case file** separately
- App compares **Cause List TEXT vs Excel FILE**
- Matching logic is **IDENTICAL** to the old app
""")

# ==================================================
# 🔒 MATCHING LOGIC (UNCHANGED – COPIED AS-IS)
# ==================================================
def extract_main_wp_cases(raw_text):
    if not raw_text.strip():
        return []

    # Remove bracketed content completely
    text = re.sub(r"\([^)]*\)", "", raw_text)

    # Remove lines containing "ARISING FROM"
    lines = text.splitlines()
    lines = [l for l in lines if "ARISING FROM" not in l.upper()]
    text = " ".join(lines)

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text)

    # Extract ONLY standalone WP cases
    matches = re.findall(
        r"\bWP\s*/\s*\d{1,6}\s*/\s*\d{2,4}\b",
        text,
        flags=re.IGNORECASE
    )

    clean_cases = []
    for m in matches:
        m = re.sub(r"\s*/\s*", "/", m)
        clean_cases.append(m.upper())

    clean_cases = sorted(set(clean_cases))
    return clean_cases


# ==================================================
# 🤖 AUTOMATIC FETCH HELPERS
# ==================================================
BOARD_URL = "https://aphc.gov.in/Hcdbs/online_board.jsp"

def fetch_uploaded_pdf_links():
    r = requests.get(BOARD_URL, timeout=20)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    table = soup.find("table")
    pdf_links = []

    if not table:
        return pdf_links

    rows = table.find_all("tr")[1:]
    for row in rows:
        row_text = row.get_text(" ", strip=True).upper()
        if "UPLOADED" not in row_text:
            continue

        link = row.find("a")
        if link and link.get("href"):
            pdf_links.append("https://aphc.gov.in" + link["href"])

    return pdf_links


def read_pdfs_to_text(pdf_links):
    combined_text = ""
    for url in pdf_links:
        pdf_bytes = requests.get(url, timeout=30).content
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    combined_text += text + "\n"
    return combined_text


# ==================================================
# 🧭 CAUSE LIST INPUT SELECTION
# ==================================================
input_mode = st.radio(
    "Cause list input method",
    ["Manual paste", "Automatic fetch"]
)

cause_text = ""

if input_mode == "Manual paste":
    cause_text = st.text_area(
        "📝 Paste Cause List Text",
        height=300,
        placeholder="Paste cause list text here..."
    )

else:
    if st.button("📥 Fetch uploaded cause lists"):
        with st.spinner("Fetching uploaded cause lists..."):
            pdf_links = fetch_uploaded_pdf_links()

            if not pdf_links:
                st.warning("No uploaded cause lists found at this moment.")
            else:
                cause_text = read_pdfs_to_text(pdf_links)
                st.success(f"Fetched {len(pdf_links)} cause list PDFs")


# ==================================================
# 📊 EXCEL UPLOAD (UNCHANGED)
# ==================================================
xls_file = st.file_uploader(
    "📊 Upload Excel File",
    type=["xlsx", "xls"]
)

# ==================================================
# 🔁 PROCESSING (UNCHANGED LOGIC)
# ==================================================
if cause_text and xls_file:
    with st.status("Processing...", expanded=True):

        main_cases = extract_main_wp_cases(cause_text)
        main_case_set = set(main_cases)

        xls = pd.ExcelFile(xls_file)
        all_matches = []

        for sheet in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet)
            df.columns = [c.lower().strip() for c in df.columns]

            case_col = next(
                (c for c in df.columns if c in ["case no", "caseno", "case number"]),
                None
            )
            year_col = next(
                (c for c in df.columns if c in ["case year", "year"]),
                None
            )

            if not case_col or not year_col:
                continue

            df[case_col] = df[case_col].astype(str)
            df = df[~df[case_col].str.strip().eq("")]
            if df.empty:
                continue

            df[case_col] = df[case_col].str.replace(r"\s+", "", regex=True)

            year_series = pd.to_numeric(df[year_col], errors="coerce")
            if year_series.notna().any():
                detected_year = int(year_series.dropna().iloc[0])
            else:
                sheet_year_match = re.search(r"\b(19|20)\d{2}\b", sheet)
                if sheet_year_match:
                    detected_year = int(sheet_year_match.group())
                else:
                    continue

            df[year_col] = year_series.fillna(detected_year).astype(int)

            df["Temp_FullCase"] = (
                "WP/" +
                df[case_col] +
                "/" +
                df[year_col].astype(str)
            ).str.upper()

            matches = df[df["Temp_FullCase"].isin(main_case_set)].copy()
            if not matches.empty:
                matches["Sheet_Source"] = sheet
                all_matches.append(matches)

        st.success("Processing completed")

    if all_matches:
        final_df = pd.concat(all_matches, ignore_index=True)
        final_df.drop(columns=["Temp_FullCase"], inplace=True)

        st.success(f"✅ {len(final_df)} matching MAIN cases found")
        st.dataframe(final_df, use_container_width=True)

        csv = final_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 Download Matched Cases (CSV)",
            data=csv,
            file_name="aphc_main_cases_only_auto.csv",
            mime="text/csv"
        )
    else:
        st.warning("❌ No matching MAIN cases found.")

else:
    st.info("⬆️ Provide cause list (manual or automatic) and upload Excel to continue.")
