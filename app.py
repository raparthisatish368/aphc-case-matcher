import streamlit as st
import pandas as pd
import re

# --------------------------------------------------
# Page Config
# --------------------------------------------------
st.set_page_config(
    page_title="APHC Case Matcher – Main Cases Only",
    page_icon="⚖️",
    layout="wide"
)

# --------------------------------------------------
# Extract ONLY standalone main WP cases
# --------------------------------------------------
def extract_main_wp_cases(raw_text):
    if not raw_text.strip():
        return []

    # --------------------------------------------------
    # STEP 1: Remove ALL bracketed content completely
    # Removes: (WP/10/2024), (SR), (anything)
    # --------------------------------------------------
    text = re.sub(r"\([^)]*\)", "", raw_text)

    # --------------------------------------------------
    # STEP 2: Remove lines containing "ARISING FROM"
    # --------------------------------------------------
    lines = text.splitlines()
    lines = [l for l in lines if "ARISING FROM" not in l.upper()]
    text = " ".join(lines)

    # --------------------------------------------------
    # STEP 3: Normalize whitespace
    # --------------------------------------------------
    text = re.sub(r"\s+", " ", text)

    # --------------------------------------------------
    # STEP 4: Extract ONLY clean standalone WP cases
    # Word boundary at end ensures no trailing ')'
    # --------------------------------------------------
    wp_pattern = r"\bWP\s*/\s*\d{1,6}\s*/\s*\d{2,4}\b"
    cases = re.findall(wp_pattern, text, flags=re.IGNORECASE)

    # --------------------------------------------------
    # STEP 5: Normalize & deduplicate
    # --------------------------------------------------
    clean_cases = []
    for c in cases:
        c = re.sub(r"\s*/\s*", "/", c)
        clean_cases.append(c.upper())

    clean_cases = sorted(set(clean_cases))

    # DEBUG OUTPUT
    st.write("### 📄 Cause List Debug (MAIN CASES ONLY)")
    st.write(f"Main WP cases extracted: **{len(clean_cases)}**")
    if clean_cases:
        st.write(clean_cases)

    return clean_cases

# --------------------------------------------------
# UI
# -------------------------------
