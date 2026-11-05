
    
  
            skipped_rows.append({
                "Sheet": sheet,
                "Row_Index": idx,
                "Case_No": raw_case_values.loc[idx],
                "Year": df.loc[idx, year_col] if year_col else None,
                "Reason": "Case No. is not numeric",
            })

        df = df[df[case_col].notna()].copy()
        df[case_col] = df[case_col].astype("Int64")
        if df.empty:
            continue

        detected_year = None
        if year_col:
            year_series = pd.to_numeric(df[year_col], errors="coerce")
            if year_series.notna().any():
                detected_year = int(year_series.dropna().iloc[0])
        else:
            year_series = pd.Series(index=df.index, dtype="float64")

        if detected_year is None:
            year_match = re.search(r"(19|20)\d{2}", str(sheet))
            if year_match:
                detected_year = int(year_match.group())

        df["__year"] = year_series
        if detected_year is not None:
            df["__year"] = df["__year"].fillna(detected_year)

        valid_indices = []
        full_cases = []
        for idx, row in df.iterrows():
            case_value = row[case_col]
            year_value = row["__year"]
            try:
                if pd.isna(year_value):
                    raise ValueError("Missing case year")
                case_number = int(case_value)
                case_year = int(year_value)
                full_case = f"{case_type}/{case_number}/{case_year}"
                valid_indices.append(idx)
                full_cases.append(full_case)
            except (ValueError, TypeError, OverflowError):
                skipped_rows.append({
                    "Sheet": sheet,
                    "Row_Index": idx,
                    "Case_No": case_value,
                    "Year": year_value,
                    "Reason": "Invalid or missing case year",
                })

        df = df.loc[valid_indices].copy()
        df["__fullcase"] = full_cases
        hit = df[df["__fullcase"].isin(main_cases)].copy()
        if not hit.empty:
            hit["Sheet"] = sheet
            matched_cases.update(hit["__fullcase"])
            results.append(hit)

    # --------------------------------------------------
    # DISPLAY MATCHED RESULTS
    # --------------------------------------------------
    if results:
        final = pd.concat(results, ignore_index=True)
        final.drop(columns=["__fullcase", "__year"], inplace=True, errors="ignore")
        st.success(f"✅ Matched Rows: {len(final)}")
        st.dataframe(final, use_container_width=True)
    else:
        st.warning("No matches found.")
        final = pd.DataFrame()

    # --------------------------------------------------
    # UNMATCHED CASES
    # --------------------------------------------------
    unmatched = main_cases - matched_cases
    st.write(f"❌ Unmatched Cases: {len(unmatched)}")
    if unmatched:
        st.write(sorted(unmatched)[:50])

    # --------------------------------------------------
    # SKIPPED ROWS
    # --------------------------------------------------
    skipped_df = pd.DataFrame(skipped_rows)
    if not skipped_df.empty:
        st.warning(f"⚠️ Skipped Rows: {len(skipped_df)}")
        st.dataframe(skipped_df, use_container_width=True)

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
        data=output.getvalue(),
        file_name="final_output.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
else:
    st.info("Provide cause list input and upload an Excel file.")

