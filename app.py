import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
import re

st.set_page_config(page_title="APHC Matcher", page_icon="⚖️")

def extract_cases_from_pdf(pdf_file):
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text() + "\n"

    # All WP case numbers like WP/12345/2017
    wp_pattern = r"(WP/\d{1,5}/\d{4})"
    all_wp_matches = re.findall(wp_pattern, text)

    # Cases that appear as ARISING FROM (to exclude)
    arising_pattern = r"ARISING FROM\s*[\(\n\r]*\s*(WP/\d{1,5}/\d{4})"
    arising_matches = re.findall(arising_pattern, text)

    arising_set = set(arising_matches)
    final_cases = sorted(list(set([c for c in all_wp_matches if c not in arising_set])))
    return final_cases

st.title("⚖️ APHC Case Matcher")
st.markdown("Upload Cause List PDF and Master Excel to get matching cases by case number + year.")

col1, col2 = st.columns(2)
with col1:
    pdf_file = st.file_uploader("1️⃣ Cause List (PDF)", type=["pdf"])
with col2:
    xls_file = st.file_uploader("2️⃣ Master Excel (.xlsx / .xls)", type=["xlsx", "xls"])

if pdf_file and xls_file:
    with st.status("Processing...", expanded=True) as status:
        st.write("📄 Reading PDF...")
        cause_list_cases = extract_cases_from_pdf(pdf_file)
        st.write(f"Found **{len(cause_list_cases)}** cases in cause list.")

        st.write("📊 Reading Excel sheets...")
        xls = pd.ExcelFile(xls_file)
        all_matches = []

        for sheet_name in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet_name)
            # Normalize column names
            df.columns = [str(c).strip().lower() for c in df.columns]

            # Try to find Case No and Year columns
            case_col = next((c for c in df.columns if "case" in c and "no" in c), None)
            year_col = next((c for c in df.columns if "year" in c), None)

            if case_col and year_col:
                # Build WP/CaseNo/Year for matching
                df["Temp_FullCase"] = df.apply(
                    lambda x: f"WP/{str(x[case_col]).strip()}/{str(x[year_col]).strip()}",
                    axis=1
                )
                mask = df["Temp_FullCase"].isin(cause_list_cases)
                matches = df[mask].copy()
                if not matches.empty:
                    matches["Sheet_Source"] = sheet_name
                    all_matches.append(matches)

        status.update(label="Done", state="complete", expanded=False)

    if all_matches:
        final_df = pd.concat(all_matches, ignore_index=True)
        if "Temp_FullCase" in final_df.columns:
            final_df = final_df.drop(columns=["Temp_FullCase"])
        st.success(f"✅ {len(final_df)} matching rows found.")
        st.dataframe(final_df)
        csv = final_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 Download matches as CSV",
            data=csv,
            file_name="matched_cases.csv",
            mime="text/csv"
        )
    else:
        st.warning("No matches found. Check case/year columns and case format in Excel.")
else:
    st.info("Please upload both files above to start.")
