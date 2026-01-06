def extract_cases_from_pdf(pdf_file):
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text() + "\n"

    # 1. Regex for ANY WP number (WP/12345/2017)
    wp_pattern = r"WP/\d{1,5}/\d{4}"
    
    # 2. Regex for WP numbers inside parentheses: (WP/12345/2017)
    #    This catches the "ARISING FROM" cases
    arising_pattern = r"\(WP/\d{1,5}/\d{4}\)"
    
    # Get all matches
    all_matches = re.findall(wp_pattern, text)
    
    # Get arising matches (returns strings like "(WP/123/2017)")
    arising_matches_raw = re.findall(arising_pattern, text)
    
    # Clean the brackets to get just the numbers for exclusion
    arising_clean = set([m.replace("(", "").replace(")", "") for m in arising_matches_raw])
    
    # Filter: Keep if NOT in the arising set
    final_cases = sorted(list(set([c for c in all_matches if c not in arising_clean])))
    
    return final_cases
