import streamlit as st
import pandas as pd
import re

# --------------------------------------------------
# Page setup
# --------------------------------------------------
st.set_page_config(
    page_title="APHC Case Matcher",
    page_icon="⚖️",
    layout="wide"
)

st.title("⚖️ APHC Case Matcher")

st.markdown("""
### Rules
- Extract only main WP cases
- Ignore bracket content `( )`
- Case number:
  - Blank → skipped
  - Spaces removed (`1 2 → 12`)
- Year:
  - Use first available year
  - Else take from sheet name
""")

# --------------------------------------------------
# Extract WP cases
# --------------------------------------------------
def extract_main_wp_cases(text):
    if not text.strip():
        return []

    text = re.sub(r"\([^)]*\)", "", text)
    text = re.sub(r"\s+", " ", text)

    matches = re.findall(r"WP\s*/\s*\d+\s*/\s*\d+", text, re.I)

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
# UI
# --------------------------------------------------
cause_text = st.text_area("📝 Paste Cause List Text", height=250)
excel_file = st.file_uploader("📊 Upload Excel", type=["xlsx", "xls"])

# --------------------------------------------------
# Processing
# --------------------------------------------------
if cause_text and excel_file:

    main_cases = extract_main_wp_cases(cause_text)
    main_case_set = set(main_cases)

    st.write("### Extracted Cases")
    st.write(main_cases[:20])

    xls = pd.ExcelFile(excel_file)
    all_matches = []

    for sheet in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name=sheet)

        # Normalize column names
        df.columns = [c.lower().strip() for c in df.columns]

        # Detect columns
        case_col = next((c for c in df.columns if "case" in c), None)
        year_col = next((c for c in df.columns if "year" in c), None)

        if not case_col or not year_col:
            continue

        # -------------------------
        # Clean case numbers
        # -------------------------
        df[case_col] = df[case_col].astype(str)
        df = df[~df[case_col].str.strip().eq("")]

        if df.empty:
            continue

        df[case_col] = df[case_col].str.replace(r"\s+", "", regex=True)

        # -------------------------
        # Handle year
        # -------------------------
        year_series = pd.to_numeric(df[year_col], errors="coerce")

        if year_series.notna().any():
            detected_year = int(year_series.dropna().iloc[0])
        else:
            match = re.search(r"(19|20)\d{2}", str(sheet))
            if match:
                detected_year = int(match.group())
            else:
                continue

        df[year_col] = year_series.fillna(detected_year)

        # -------------------------
        # Final normalization
        # -------------------------
        case_series = pd.to_numeric(df[case_col], errors="coerce")
        year_series = pd.to_numeric(df[year_col], errors="coerce")

        # Remove invalid rows safely
        valid_mask = case_series.notna() & year_series.notna()
        df = df[valid_mask]
        case_series = case_series[valid_mask]
        year_series = year_series[valid_mask]

        if df.empty:
            continue

        df["Temp_FullCase"] = (
            "WP/" +
            case_series.astype("Int64").astype(str) +
            "/" +
            year_series.astype("Int64").astype(str)
        )

        # -------------------------
        # Matching
        # -------------------------
        matches = df[df["Temp_FullCase"].isin(main_case_set)].copy()

        if not matches.empty:
            matches["Sheet"] = sheet
            all_matches.append(matches)

    # -------------------------
    # Output
    # -------------------------
    if all_matches:
        final_df = pd.concat(all_matches, ignore_index=True)
        final_df.drop(columns=["Temp_FullCase"], inplace=True)

        st.success(f"✅ {len(final_df)} matches found")
        st.dataframe(final_df)

        csv = final_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 Download CSV",
            data=csv,
            file_name="matched_cases.csv",
            mime="text/csv"
        )
    else:
        st.warning("❌ No matches found")

else:
    st.info("⬆️ Paste text and upload Excel to start")
