import streamlit as st
import pandas as pd
import re
import requests
import pdfplumber
import io
import urllib3

# --------------------------------------------------
# SSL warning suppression (safe for public PDFs)
# --------------------------------------------------
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (APHC-Case-Matcher)"
}

# --------------------------------------------------
# Page configuration
# --------------------------------------------------
st.set_page_config(
    page_title="APHC Case Matcher – Main Cases Only",
    page_icon="⚖️",
    layout="wide"
)

st.title("⚖️ APHC Case Matcher (PDF Link / Manual Paste)")

st.markdown("""
### How to use
1. **Preferred**: Paste **cause list PDF link(s)** (one per line)  
2. **Backup**: Paste cause list text manually  
3. Upload **Excel case file**  
4. App matches **MAIN WP cases only**
""")

# ==================================================
# 🔒 MATCHING LOGIC (UNCHANGED – YOUR ORIGINAL CODE)
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

    return sorted(set(clean_cases))

# ==================================================
# 📥 PDF LINK → TEXT (PRIMARY AUTOMATION)
# ==================================================
def read_pdfs_to_text(pdf_urls):
    collected_text = []

    for url in pdf_urls:
        try:
            r = requests.get(
                url,
                headers=HEADERS,
                timeout=30,
                verify=False
            )
            r.raise_for_status()

            with pdfplumber.open(io.BytesIO(r.content)) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        collected_text.append(text)

        except Exception:
            st.warning(f"⚠️ Unable to read PDF: {url}")

    return "\n".join(collected_text)

# ==================================================
# 🧾 CAUSE LIST INPUT
# ==================================================
st.markdown("## 🧾 Cause List Input")

input_mode = st.radio(
    "Choose input method",
    ["Paste PDF link(s) (recommended)", "Manual paste (backup)"]
)

cause_text = ""

# -------------------------------
# OPTION 1: PDF LINKS
# -------------------------------
if input_mode == "Paste PDF link(s) (recommended)":
    pdf_links_text = st.text_area(
        "🔗 Paste cause list PDF link(s) — one per line",
        height=150,
        placeholder=(
            "Example:\n"
            "https://aphc.gov.in/.../court_1_causelist.pdf\n"
            "https://aphc.gov.in/.../court_2_causelist.pdf"
        )
    )

    if pdf_links_text and st.button("📥 Download & read PDFs"):
        pdf_links = [
            line.strip()
            for line in pdf_links_text.splitlines()
            if line.strip().startswith("http")
        ]

        if not pdf_links:
            st.error("No valid PDF links found.")
        else:
            with st.spinner("Downloading and extracting PDF text..."):
                cause_text = read_pdfs_to_text(pdf_links)

            if cause_text.strip():
                st.success("PDF text extracted successfully.")
            else:
                st.warning("No readable text found in PDFs.")

# -------------------------------
# OPTION 2: MANUAL PASTE
# -------------------------------
else:
    cause_text = st.text_area(
        "📝 Paste cause list text (from APHC website)",
        height=300,
        placeholder=(
            "APHC → Daily Cause List → Court wise → Court No.\n"
            "Select all visible text and paste here."
        )
    )

# ==================================================
# 📊 EXCEL INPUT (UNCHANGED)
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
            file_name="aphc_main_cases_only.csv",
            mime="text/csv"
        )
    else:
        st.warning("❌ No matching MAIN cases found.")

else:
    st.info("⬆️ Provide cause list (PDF link or manual paste) and upload Excel to continue.")
