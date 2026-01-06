import streamlit as st
import pandas as pd
import re

# --------------------------------------------------
# Page Config
# --------------------------------------------------
st.set_page_config(
    page_title="APHC Case Matcher",
    page_icon="⚖️",
    layout="wide"
)

# --------------------------------------------------
# Extract WP cases from pasted text
# --------------------------------------------------
def extract_cases_from_text(raw_text):
    if not raw_text.strip():
        return []

    text = re.sub(r"\s+", " ", raw_text)

    wp_pattern = r"\bWP\s*/\s*\d{1,6}\s*/\s*\d{2,4}(?=\D|$)"
    cases = re.findall(wp_pattern, text, flags=re.IGNORECASE)

    clean = []
    for c in cases:
        c = re.sub(r"\s*/\s*", "/", c)
        clean.append(c.upper())

    clean = sorted(set(clean))

    st.write("### 📄 Cause List Debug")
    st.write(f"WP cases found: **{len(clean)}**")
    if clean:
        st.write("Sample:", clean[:5])

    return clean

# --------------------------------------------------
# UI
# --------------------------------------------------
st.title("⚖️ APHC Case Matcher")
st.markdown(
    """
**Step 1:** Copy cause list text and paste below  
**Step 2:** Upload your Excel (year-wise sheets)
"""
)

cause_text = st.text_area(
    "📝 Paste Cause List Text",
    height=300
)

xls_file = st.file_uploader(
    "📊 Upload Excel File",
    type=["xlsx", "xls"]
)

# --------------------------------------------------
# Processing
# --------------------------------------------------
if cause_text and xls_file:
    with st.status("Processing...", expanded=True):

        cause_cases = extract_cases_from_text(cause_text)
        cause_set = set(cause_cases)

        st.write("📊 Reading Excel sheets...")
        xls = pd.ExcelFile(xls_file)
        all_matches = []

        for sheet in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet)

            # Normalize column names
            df.columns = [c.lower().strip() for c in df.columns]

            # 🔥 DETECT YOUR REAL COLUMNS
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

            # Build WP/xxx/yyyy
            df["Temp_FullCase"] = (
                "WP/" +
                df[case_col].astype(str).str.strip() +
                "/" +
                df[year_col].astype(str).str.strip()
            ).str.upper()

            # DEBUG (first valid sheet only)
            if sheet == xls.sheet_names[0]:
                st.write("### 📊 Excel Debug")
                st.write(df["Temp_FullCase"].head(5).tolist())

            matches = df[df["Temp_FullCase"].isin(cause_set)].copy()

            if not matches.empty:
                matches["Sheet_Source"] = sheet
                all_matches.append(matches)

        st.success("Processing completed")

    # --------------------------------------------------
    # Results
    # --------------------------------------------------
    if all_matches:
        final_df = pd.concat(all_matches, ignore_index=True)
        final_df.drop(columns=["Temp_FullCase"], inplace=True)

        st.success(f"✅ {len(final_df)} matching cases found")
        st.dataframe(final_df, use_container_width=True)

        csv = final_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 Download Matches (CSV)",
            data=csv,
            file_name="aphc_matched_cases.csv",
            mime="text/csv"
        )
    else:
        st.warning("❌ No matches found. Please verify pasted cause list.")

else:
    st.info("⬆️ Paste cause list text and upload Excel to continue.")
