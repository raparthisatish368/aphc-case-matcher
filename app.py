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
# Case Extraction from Text
# --------------------------------------------------
def extract_cases_from_text(raw_text):
    if not raw_text.strip():
        return []

    # Normalize whitespace (important for copied court text)
    text = re.sub(r"\s+", " ", raw_text)

    # Regex that excludes parentheses and trailing junk
    wp_pattern = r"\bWP/\d{1,6}/\d{2,4}(?=\D|$)"
    cases = re.findall(wp_pattern, text, flags=re.IGNORECASE)

    # Normalize + deduplicate
    cases = sorted(set(c.upper().strip() for c in cases))

    # Debug info
    st.write("### 📄 Cause List Text Analysis")
    st.write(f"Total unique WP cases found: **{len(cases)}**")
    if cases:
        st.write("Sample cases:", cases[:5])

    return cases

# --------------------------------------------------
# UI
# --------------------------------------------------
st.title("⚖️ APHC Case Matcher (Text Input)")
st.markdown(
    """
### Step 1  
Copy the **cause list text** from APHC website / PDF and paste it below.

### Step 2  
Upload your **Master Excel file**.

The app will instantly show **matching WP cases**.
"""
)

# Text input for cause list
cause_text = st.text_area(
    "📝 Paste Cause List Text Here",
    height=300,
    placeholder="Paste copied cause list content here..."
)

# Excel upload
xls_file = st.file_uploader(
    "📊 Upload Master Excel (.xlsx / .xls)",
    type=["xlsx", "xls"]
)

# --------------------------------------------------
# Processing
# --------------------------------------------------
if cause_text and xls_file:
    with st.status("Processing...", expanded=True):

        st.write("📄 Extracting cases from pasted text...")
        cause_list_cases = extract_cases_from_text(cause_text)
        cause_set = set(cause_list_cases)

        st.write("📊 Reading Excel sheets...")
        xls = pd.ExcelFile(xls_file)
        all_matches = []

        for sheet_name in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet_name)
            df.columns = [str(c).strip().lower() for c in df.columns]

            # Auto-detect columns
            case_col = next(
                (c for c in df.columns if "case" in c and "no" in c),
                None
            )
            year_col = next(
                (c for c in df.columns if "year" in c),
                None
            )

            if case_col and year_col:
                df["Temp_FullCase"] = (
                    "WP/" +
                    df[case_col].astype(str).str.strip() +
                    "/" +
                    df[year_col].astype(str).str.strip()
                )

                # Normalize
                df["Temp_FullCase"] = (
                    df["Temp_FullCase"]
                    .str.upper()
                    .str.replace(r"\.0$", "", regex=True)
                )

                mask = df["Temp_FullCase"].isin(cause_set)
                matches = df.loc[mask].copy()

                if not matches.empty:
                    matches["Sheet_Source"] = sheet_name
                    all_matches.append(matches)

        st.success("Processing completed")

    # --------------------------------------------------
    # Results
    # --------------------------------------------------
    if all_matches:
        final_df = pd.concat(all_matches, ignore_index=True)

        if "Temp_FullCase" in final_df.columns:
            final_df.drop(columns=["Temp_FullCase"], inplace=True)

        st.success(f"✅ {len(final_df)} matching rows found")
        st.dataframe(final_df, use_container_width=True)

        csv = final_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 Download Matched Cases (CSV)",
            data=csv,
            file_name="aphc_matched_cases.csv",
            mime="text/csv"
        )
    else:
        st.warning("❌ No matching cases found. Check Excel case/year columns.")

else:
    st.info("⬆️ Paste cause list text and upload Excel to continue.")
