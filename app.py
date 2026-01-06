import streamlit as st
import pandas as pd
import re

st.set_page_config(
    page_title="APHC Case Matcher",
    page_icon="⚖️",
    layout="wide"
)

st.title("⚖️ APHC Case Matcher – Main Cases Only")

st.markdown("""
**Rules applied**
- Only standalone main WP cases
- Ignore anything in brackets `( )`
- Ignore `ARISING FROM` cases
""")

# --------------------------------------------------
# Extraction logic (SAFE)
# --------------------------------------------------
def extract_main_wp_cases(text):
    try:
        # Remove bracketed content
        text = re.sub(r"\([^)]*\)", "", text)

        # Remove ARISING FROM lines
        lines = text.splitlines()
        lines = [l for l in lines if "ARISING FROM" not in l.upper()]
        text = " ".join(lines)

        # Normalize whitespace
        text = re.sub(r"\s+", " ", text)

        # Extract WP cases
        matches = re.findall(r"WP\s*/\s*\d{1,6}\s*/\s*\d{2,4}", text, flags=re.I)

        # Normalize
        clean = []
        for m in matches:
            m = re.sub(r"\s*/\s*", "/", m)
            clean.append(m.upper())

        return sorted(set(clean))
    except Exception as e:
        st.error("Error while extracting cases")
        st.exception(e)
        return []

# --------------------------------------------------
# UI Inputs
# --------------------------------------------------
cause_text = st.text_area(
    "📝 Paste Cause List Text",
    height=300,
    placeholder="Paste cause list text here..."
)

xls_file = st.file_uploader(
    "📊 Upload Excel File",
    type=["xlsx", "xls"]
)

# --------------------------------------------------
# Processing
# --------------------------------------------------
if cause_text and xls_file:
    st.subheader("🔍 Processing")

    main_cases = extract_main_wp_cases(cause_text)
    st.write("Extracted main cases:", main_cases)

    if not main_cases:
        st.warning("No main WP cases detected.")
    else:
        df_all = []
        xls = pd.ExcelFile(xls_file)

        for sheet in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet)
            df.columns = [c.lower().strip() for c in df.columns]

            case_col = next((c for c in df.columns if "case" in c), None)
            year_col = next((c for c in df.columns if "year" in c), None)

            if not case_col or not year_col:
                continue

            df["wp"] = (
                "WP/" +
                df[case_col].astype(str).str.strip() +
                "/" +
                df[year_col].astype(str).str.strip()
            ).str.upper()

            matches = df[df["wp"].isin(main_cases)].copy()
            if not matches.empty:
                matches["sheet"] = sheet
                df_all.append(matches)

        if df_all:
            result = pd.concat(df_all, ignore_index=True)
            st.success(f"✅ {len(result)} matches found")
            st.dataframe(result)
        else:
            st.warning("No matches found in Excel.")

else:
    st.info("⬆️ Paste text and upload Excel to start.")
