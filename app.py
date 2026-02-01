import streamlit as st
import requests
from bs4 import BeautifulSoup
import pdfplumber
import io

# =====================================================
# PAGE CONFIG
# =====================================================
st.set_page_config(
    page_title="APHC Case Matcher",
    layout="wide"
)

st.title("APHC Cause List – Case Matcher")

# =====================================================
# 🔒 OLD MATCHING LOGIC (UNCHANGED)
# =====================================================
def old_matching_logic(text):
    """
    ⚠️ THIS IS YOUR EXISTING LOGIC PLACEHOLDER.
    Replace ONLY the body with your already working logic.
    DO NOT change function name or call signature.
    """
    # -----------------------------
    # EXAMPLE ONLY – replace with YOUR code
    # -----------------------------
    import re
    pattern = r"\b\d+/\d{4}\b"
    cases = sorted(set(re.findall(pattern, text)))
    return cases


# =====================================================
# INPUT MODE SELECTION
# =====================================================
mode = st.radio(
    "Choose input method",
    ["Manual (Copy–Paste)", "Automatic (Fetch from Online Board)"]
)

# =====================================================
# 🅰️ MANUAL MODE (OLD FLOW)
# =====================================================
if mode == "Manual (Copy–Paste)":
    st.subheader("Manual Copy–Paste Mode")

    pasted_text = st.text_area(
        "Paste cause list text below",
        height=350
    )

    if st.button("Process Cause List"):
        if not pasted_text.strip():
            st.warning("Please paste the cause list text.")
        else:
            result = old_matching_logic(pasted_text)
            st.success(f"Found {len(result)} matching cases")
            st.write(result)

# =====================================================
# 🅱️ AUTOMATIC MODE (NEW FLOW)
# =====================================================
else:
    st.subheader("Automatic Fetch from APHC Online Board")

    BOARD_URL = "https://aphc.gov.in/Hcdbs/online_board.jsp"

    def fetch_board_page():
        r = requests.get(BOARD_URL, timeout=15)
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")

    def extract_uploaded_pdfs(soup):
        pdfs = []

        table = soup.find("table")
        if not table:
            return pdfs

        rows = table.find_all("tr")[1:]
        for row in rows:
            cols = row.find_all("td")
            if not cols:
                continue

            row_text = row.get_text(" ", strip=True).upper()
            if "UPLOADED" not in row_text:
                continue

            link = row.find("a")
            if link and link.get("href"):
                pdfs.append({
                    "court": cols[0].get_text(strip=True),
                    "url": "https://aphc.gov.in" + link["href"]
                })

        return pdfs

    def read_pdf_text(pdf_url):
        pdf_bytes = requests.get(pdf_url, timeout=20).content
        full_text = ""

        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"

        return full_text

    if st.button("Fetch Uploaded Cause Lists"):
        try:
            with st.spinner("Fetching online board…"):
                soup = fetch_board_page()
                pdf_list = extract_uploaded_pdfs(soup)

            if not pdf_list:
                st.warning("No uploaded cause lists found.")
            else:
                st.success(f"{len(pdf_list)} cause lists found")

                selected = st.multiselect(
                    "Select courts to process",
                    pdf_list,
                    format_func=lambda x: f"Court {x['court']}"
                )

                if st.button("Process Selected Cause Lists"):
                    if not selected:
                        st.warning("Please select at least one court.")
                    else:
                        combined_text = ""
                        with st.spinner("Downloading & extracting PDFs…"):
                            for item in selected:
                                combined_text += read_pdf_text(item["url"])

                        result = old_matching_logic(combined_text)
                        st.success(f"Found {len(result)} matching cases")
                        st.write(result)

        except Exception as e:
            st.error(f"Error occurred: {e}")
