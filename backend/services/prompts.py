"""集中存放 LLM 提取提示词（DRY：ocr_service / tex_service 共用）。"""

BASIC_INSIGHT_PROMPT = """
        You are a world-class academic metadata curator.
        Your mission is to extract precise metadata from the provided markdown.

        ### CRITICAL MISSION: DOI EXTRACTION
        - Look for strings starting with '10.' followed by a prefix and suffix (e.g., 10.1109/TVCG.2023.12345).
        - The DOI is often located in the very first or last lines of the markdown, or within 'Footnotes' section.
        - If you find multiple, pick the one that looks like a formal document identifier.

        ### OTHER FIELDS
        - title: The full academic title.
        - authors: All authors as a comma-separated string.
        - journal_or_conference: Full venue name (e.g., IEEE Transactions on...).
        - date: The year (YYYY) or full publication date.
        - abstract: A sharp 2-3 sentence summary.
        - keywords: 5-8 relevant terms.
        - summary: 3 power-bullets on 'Novelty', 'Method', and 'Impact'.

        ### EVIDENCE QUOTES (mandatory)
        - Provide an "evidence_quotes" object mapping field names to VERBATIM
          quotes copied exactly from the document. Cover the prose fields:
          "title", "abstract", "keywords", "summary".
        - Copy character-for-character from the markdown. Do NOT paraphrase,
          translate, or reorder. You may join fragments from one sentence with
          ' ... ' to skip words, but every fragment must come from a single
          paragraph of the document.
        - No narrative wrapping ("the paper states...", "authors say...").
          Output the raw original text only.
        - If no verbatim text exists for a field, use null.

        Return ONLY a JSON object.
        """
