
    
  
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
# Matches standalone WP/CC and WP(AT)/CC(AT) references.
# Ignores parenthetical case references and references on
# lines containing "ARISING FROM".
# --------------------------------------------------
def extract_cases(text):
    cases = set()

    # Remove parenthetical text, except the (AT) suffix that is part
    # of a WP(AT) or CC(AT) case type.
    text = re.sub(
        r"(?<!WP)(?<!CC)\([^)]*\)",
        " ",
        text,
        flags=re.IGNORECASE,
    )

    pattern = re.compile(
        r"\b(WP|CC)(\s*\(\s*AT\s*\))?\s*/\s*(\d+)\s*/\s*(\d+)",
        re.IGNORECASE,
    )

    for line in text.splitlines():
        if "ARISING FROM" in line.upper():
            continue

        for match in pattern.finditer(line):
            case_type = match.group(1).upper()
            is_at = bool(match.group(2))
            case_number = int(match.group(3))
            case_year = int(match.group(4))
            suffix = "(AT)" if is_at else ""
            cases.add(f"{case_type}{suffix}/{case_number}/{case_year}")

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
                verify=False,
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

