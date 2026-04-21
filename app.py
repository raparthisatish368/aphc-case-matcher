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

# --------------------------------------------------
# PAGE SETUP
# --------------------------------------------------
st.set_page_config(
    page_title="APHC Case Matcher",
    page_icon="⚖️",
    layout="wide"
)

st.title("⚖️ APHC Case Matcher (PDF / Manual)")

# --------------------------------------------------
# EXTRACT CASES
# --------------------------------------------------
def extract_main_wp_cases(text):
    if not text.strip():
        return []

    # Remove bracket content
    text = re.sub(r"\([^)]*\)", "", text)

    # Remove ARISING FROM lines
    lines = text.splitlines()
    lines = [l for l in lines if "ARISING FROM" not in l.upper()]
    text = " ".join(lines)

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text)

    matches = re.findall(r"WP\s*/\s*\d{1,6}\s*/\s*\d{2,4}", text, re.I)

    clean = []
    for m in matches:
        m = re.sub(r"\s*/\s*", "/", m)
        parts = m.upper().split("/")

        try:
            case_no = str(int(parts[1]))
            year = str(int(parts[2]))
            clean.append(f"WP/{case_no}/{year}")
        except:
            continue

    return sorted(set(clean))

# --------------------------------------------------
# PDF READER
# --------------------------------------------------
def read_pdfs_to_text(urls):
    output = []

    for url in urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=30, verify=False)
            r.raise_for_status()

            with pdfplumber.open(io.BytesIO(r.content)) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        output.append(t)

        except Exception:
            st.warning(f"⚠️ Failed to read: {url}")

    return "\n".join(output)

# --------------------------------------------------
# INPUT UI
# --------------------------------------------------
mode = st.radio(
    "Choose input method",
    ["PDF link(s)", "Manual paste"]
)

cause_text = ""

if mode == "PDF link(s)":
    pdf_input = st.text_area("Paste PDF links (one per line)")

    if st.button("Read PDFs"):
        links = [l.strip() for l in pdf_input.splitlines() if l.strip().startswith("http")]

        if links:
            with st.spinner("Reading PDFs..."):
                cause_text = read_pdfs_to_text(links)

            if cause_text.strip():
                st.success("PDF text extracted")
            else:
                st.warning("No text extracted")
        else:
            st.error("Invalid links")

else:
    cause_text = st.text_area("Paste cause list text", height=300)

xls_file = st.file_uploader("Upload Excel", type=["xlsx", "xls"])

# --------------------------------------------------
# PROCESSING
# --------------------------------------------------
if cause_text and xls_file:

    main_cases = set(extract_main_wp_cases(cause_text))
    xls = pd.ExcelFile(xls_file)
    results = []

    for sheet in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name=sheet)

        df.columns = [str(c).lower().strip() for c in df.columns]

        case_col = next((c for c in df.columns if "case" in c), None)
        year_col = next((c for c in df.columns if "year" in c), None)

        if not case_col:
            continue

        # -------------------------
        # CLEAN CASE NO
        # -------------------------
        df[case_col] = df[case_col].astype(str).str.replace(r"\s+", "", regex=True)
        df = df[df[case_col].str.strip() != ""]

        if df.empty:
            continue

        # -------------------------
        # YEAR DETECTION
        # -------------------------
        detected_year = None

        if year_col:
            yr = pd.to_numeric(df[year_col], errors="coerce")
            if yr.notna().any():
                detected_year = int(yr.dropna().iloc[0])

        if not detected_year:
            m = re.search(r"(19|20)\d{2}", str(sheet))
            if m:
                detected_year = int(m.group())
            else:
                continue

        df["__year"] = detected_year

        # -------------------------
        # NORMALIZE CASE NUMBER
        # -------------------------
        case_series = pd.to_numeric(df[case_col], errors="coerce")

        valid_mask = case_series.notna()
        df = df[valid_mask]
        case_series = case_series[valid_mask]

        if df.empty:
            continue

        # -------------------------
        # BUILD MATCH KEY
        # -------------------------
        df["__fullcase"] = (
            "WP/" +
            case_series.astype("Int64").astype(str) +
            "/" +
            df["__year"].astype(str)
        ).str.upper()

        # -------------------------
        # MATCH
        # -------------------------
        hit = df[df["__fullcase"].isin(main_cases)].copy()

        if not hit.empty:
            hit["Sheet"] = sheet
            results.append(hit)

    # --------------------------------------------------
    # OUTPUT
    # --------------------------------------------------
    if results:
        out = pd.concat(results, ignore_index=True)
        out.drop(columns=["__fullcase", "__year"], inplace=True, errors="ignore")

        st.success(f"✅ {len(out)} matches found")
        st.dataframe(out)

        st.download_button(
            "Download CSV",
            out.to_csv(index=False).encode("utf-8"),
            "matched_cases.csv"
        )
    else:
        st.warning("No matches found")

else:
    st.info("Provide input and Excel")
