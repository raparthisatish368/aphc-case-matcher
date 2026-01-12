import streamlit as st
import pandas as pd
import re

# --------------------------------------------------
# Page configuration
# --------------------------------------------------
st.set_page_config(
    page_title="APHC Case Matcher – Main Cases Only",
    page_icon="⚖️",
    layout="wide"
)

st.title("⚖️ APHC Case Matcher (Main Cases Only)")

st.markdown("""
### Rules applied
- ✅ Extract **only main WP cases**
- ❌ Ignore anything inside `( )`
- ❌ Ignore **ARISING FROM** cases
- ✅ Case No:
  - Blank cell → skipped
  - Spaces allowed → spaces removed (`"1 2"` → `12`)
- ✅ Year:
  - If **any row** has a year → that year is applied to the whole sheet
  - If no year anywhere → sheet skipped
""")

# --------------------------------------------------
# Extract ONLY standalone main WP cases from text
# --------------------------------------------------
def extract_main_wp_cases(raw_text):
    if not raw_text.strip():
        return []

    # Remove all bracketed content
    text = re.sub(r"\([^)]*\)", "", raw_text)

    # Remove lines containing "ARISING FROM"
    lines = text.splitlines()
    lines = [l for l in lines if "ARISING FROM" not in l.upper()]
    text = " ".join(lines)

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text)

    # Extract standalone WP cases only
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

    st.write("### 📄 Cause List Debug")
    st.write(f"Main WP cases extracted: **{len(clean_cases)}**")
    if clean_cases:
        st.write(clean_cases)

    return clean_cases

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
    with st.status("Processing...", expanded=True):

        main_cases = extract_main_wp_cases(cause_text)
        main_case_set = set(main_cases)

        xls = pd.ExcelFile(xls_file)
        all_matches = []

        for sheet in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet)

            # Normalize column names
            df.columns = [c.lower().strip() for c in df.columns]

            # Detect columns
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

            # --------------------------------------------------
            # CASE NO LOGIC
            # - Skip only if completely blank
            # - Remove all spaces
            # --------------------------------------------------
            df[case_col] = df[case_col].astype(str)
            df = df[~df[case_col].str.strip().eq("")]

            if df.empty:
                continue

            df[case_col] = df[case_col].str.replace(r"\s+", "", regex=True)

            # --------------------------------------------------
            # YEAR LOGIC (sheet-level)
            # --------------------------------------------------
            year_series = pd.to_numeric(df[year_col], errors="coerce")

            if not year_series.notna().any():
                continue  # no year anywhere in this sheet

            detected_year = int(year_series.dropna().iloc[0])
            df[year_col] = year_series.fillna(detected_year).astype(int)

            # --------------------------------------------------
            # Build comparison key
            # --------------------------------------------------
            df["Temp_FullCase"] = (
                "WP/" +
                df[case_col] +
                "/" +
                df[year_col].astype(str)
            ).str.upper()

            # Match
            matches = df[df["Temp_FullCase"].isin(main_case_set)].copy()

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
    st.info("⬆️ Paste cause list text and upload Excel to continue.")
