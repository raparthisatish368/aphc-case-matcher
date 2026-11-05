
    
  

        if year_col:
            year_series = pd.to_numeric(df[year_col], errors="coerce")
            if year_series.notna().any():
                detected_year = int(year_series.dropna().iloc[0])

        if not detected_year:
            year_match = re.search(r"(19|20)\d{2}", str(sheet))
            if year_match:
                detected_year = int(year_match.group())

        if year_series is not None:
            df["__year"] = year_series
        else:
            df["__year"] = None

        if detected_year:
            df["__year"] = df["__year"].fillna(detected_year)

        df["__year"] = pd.to_numeric(df["__year"], errors="coerce")

        # --------------------------------------------------
        # BUILD FULL CASE AND VALIDATE ROWS
        # --------------------------------------------------
        valid_indices = []
        full_cases = []

        for row_index, row in df.iterrows():
            case_value = row[case_col]
            year_value = row["__year"]

            if pd.isna(year_value):
                year_value = detected_year

            try:
                case_number = int(case_value)

                if pd.isna(year_value):
                    raise ValueError("Missing year")

                year_number = int(year_value)
                full_case = f"{sheet_case_type}/{case_number}/{year_number}"

                valid_indices.append(row_index)
                full_cases.append(full_case)

            except Exception:
                skipped_rows.append({
                    "Sheet": sheet,
                    "Excel_Row": int(row_index) + 2,
                    "Case_No": case_value,
                    "Year": year_value,
                    "Reason": "Invalid case number or missing/invalid year",
                })

        df = df.loc[valid_indices].copy()
        df["__fullcase"] = full_cases

        # --------------------------------------------------
        # MATCHING
        # --------------------------------------------------
        hit = df[df["__fullcase"].isin(main_cases)].copy()

        if not hit.empty:
            hit["Sheet"] = sheet
            matched_cases.update(hit["__fullcase"])
            results.append(hit)

    # --------------------------------------------------
    # FINAL RESULT
    # --------------------------------------------------
    if results:
        final = pd.concat(results, ignore_index=True)
        final.drop(columns=["__fullcase", "__year"], inplace=True, errors="ignore")
        st.success(f"✅ Matched Rows: {len(final)}")
        st.dataframe(final)
    else:
        st.warning("No matches found")
        final = pd.DataFrame()

    # --------------------------------------------------
    # UNMATCHED
    # --------------------------------------------------
    unmatched = main_cases - matched_cases
    st.write(f"❌ Unmatched Cases: {len(unmatched)}")
    st.write(sorted(unmatched)[:20])

    # --------------------------------------------------
    # SKIPPED ROWS
    # --------------------------------------------------
    if skipped_rows:
        st.warning(f"⚠️ Skipped Rows: {len(skipped_rows)}")
        skipped_df = pd.DataFrame(skipped_rows)
        st.dataframe(skipped_df)
    else:
        skipped_df = pd.DataFrame()

    # --------------------------------------------------
    # EXCEL DOWNLOAD
    # --------------------------------------------------
    output = BytesIO()

    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        if not final.empty:
            final.to_excel(writer, index=False, sheet_name="Matched")
        else:
            pd.DataFrame({"Message": ["No matched cases"]}).to_excel(
                writer, index=False, sheet_name="Matched"
            )

        pd.DataFrame({"Unmatched": sorted(unmatched)}).to_excel(
            writer, index=False, sheet_name="Unmatched"
        )

        if not skipped_df.empty:
            skipped_df.to_excel(writer, index=False, sheet_name="Skipped Rows")

    st.download_button(
        "📥 Download Excel",
        output.getvalue(),
        "final_output.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

else:
    st.info("Provide cause-list input and upload Excel.")

