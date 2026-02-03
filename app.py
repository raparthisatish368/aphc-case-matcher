import streamlit as st
import pandas as pd
import re
import requests
import pdfplumber
import io
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (APHC-Case-Matcher)"
}

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
# MAIN WP EXTRACTION (UNCHANGED LOGIC)
# ==================================================
def extract_main_wp_cases(raw_text):
    if not raw_text.strip():
        return []

    text = re.sub(r"\([^)]*\)", "", raw_text)

    lines = text.splitlines()
    lines = [l for l in lines if "ARISING FROM" not in l.upper()]
    text = " ".join(lines)

    text = re.sub(r"\s+", " ", text)

    matches = re.findall(
        r"\bWP\s*/\s*\d{1,6}\s*/\s*\d{2,4}\b",
        text,
        flags=re.IGNORECASE
    )

    clean = []
    for m in matches:
        m = re.sub(r"\s*/\s*", "/", m)
        clean.append(m.upper())

    return sorted(set(clean))

# ==================================================
# PDF LINKS → TEXT
# ==================================================
def read_pdfs_to_text(pdf_urls):
    output = []

    for url in pdf_urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=30, verify=False)
            r.raise_for_status()

            with pdfplumber.open(io.BytesIO(r.content)) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        output.append(t)

        except Exception:
            st.warning(f"⚠️ Could not read PDF: {url}")

    return "\n".join(output)

# ==================================================
# INPUT SECTION
# ==================================================
st.markdown("## 🧾 Cause List Input")

mode = st.radio(
    "Choose input method",
    ["Paste PDF link(s) (recommended)", "Manual paste (backup)"]
)

cause_text = ""

if mode == "Paste PDF link(s) (recommended)":
    pdf_links_text = st.text_area(
        "🔗 Paste cause list PDF link(s) — one per line",
        height=150
    )

    if pdf_links_text and st.button("📥 Download & read PDFs"):
        links = [
            l.strip()
            for l in pdf_links_text.splitlines()
            if l.strip().startswith("http")
        ]

        if links:
            with st.spinner("Reading PDFs..."):
                cause_text = read_pdfs_to_text(links)

            if cause_text.strip():
                st.success("PDF text extracted successfully.")
            else:
                st.warning("No readable text in PDFs.")
        else:
            st.error("No valid PDF links found.")

else:
    cause_text = st.text_area(
        "📝 Paste cause list text",
        height=300
    )

xls_file = st.file_uploader(
    "📊 Upload Excel File",
    type=["xlsx", "xls"]
)

# ==================================================
# PROCESSING (FULLY HARDENED)
# ==================================================
if cause_text and xls_file:
    with st.status("Processing...", expanded=True):

        main_cases = set(extract_main_wp_cases(cause_text))
        xls = pd.ExcelFile(xls_file)
        results = []

        for sheet in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet)

            # ✅ SAFE COLUMN NORMALIZATION
            df.columns = [str(c).lower().strip() for c in df.columns]

            case_col = next(
                (c for c in df.columns if c in ["case no", "caseno", "case number"]),
                None
            )
            year_col = next(
                (c for c in df.columns if c in ["case year", "year"]),
                None
            )

            if not case_col:
                continue

            df[case_col] = df[case_col].astype(str).str.replace(r"\s+", "", regex=True)
            df = df[df[case_col].str.strip() != ""]

            if df.empty:
                continue

            # ---------- YEAR HANDLING (BULLETPROOF) ----------
            detected_year = None

            if year_col:
                yr = pd.to_numeric(df[year_col], errors="coerce")
                if yr.notna().any():
                    detected_year = int(yr.dropna().iloc[0])

            if not detected_year:
                m = re.search(r"\b(19|20)\d{2}\b", sheet)
                if m:
                    detected_year = int(m.group())
                else:
                    continue  # skip sheet safely

            df["__year"] = detected_year

            # ---------- BUILD MATCH KEY ----------
            df["__fullcase"] = (
                "WP/" + df[case_col] + "/" + df["__year"].astype(str)
            ).str.upper()

            hit = df[df["__fullcase"].isin(main_cases)].copy()
            if not hit.empty:
                hit["Sheet_Source"] = sheet
                results.append(hit)

        st.success("Processing completed")

    if results:
        out = pd.concat(results, ignore_index=True)
        out.drop(columns=["__fullcase", "__year"], inplace=True, errors="ignore")

        st.success(f"✅ {len(out)} matching MAIN cases found")
        st.dataframe(out, use_container_width=True)

        st.download_button(
            "📥 Download Matched Cases (CSV)",
            out.to_csv(index=False).encode("utf-8"),
            "aphc_main_cases_only.csv",
            "text/csv"
        )
    else:
        st.warning("❌ No matching MAIN cases found.")

else:
    st.info("⬆️ Provide cause list and upload Excel to continue.")
