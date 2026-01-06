def extract_cases_from_pdf(pdf_file):
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text() + "\n"

    # 1) All WP cases
    wp_pattern = r"WP/\d{1,6}/\d{4}"
    all_wp = re.findall(wp_pattern, text)

    # 2) WP cases inside parentheses: (WP/xxxx/xxxx)
    paren_pattern = r"\(WP/\d{1,6}/\d{4}\)"
    paren_raw = re.findall(paren_pattern, text)          # e.g. "(WP/14313/2017)"

    # Clean parentheses to same format as all_wp
    paren_clean = [s.strip("()") for s in paren_raw]     # e.g. "WP/14313/2017"

    # 3) Final = all WP minus those found in parentheses
    final_set = set(all_wp) - set(paren_clean)
    return sorted(final_set)
