import hashlib
import re
from collections import Counter

WORD_PATTERN = re.compile(r"\w+", re.UNICODE)


def analyze_document(document_id: str, text: str) -> dict:
    words = WORD_PATTERN.findall(text.lower())
    frequencies = Counter(words)
    return {
        "document_id": document_id,
        "word_count": len(words),
        "unique_word_count": len(frequencies),
        "top_words": [{"word": word, "count": count} for word, count in sorted(frequencies.items(), key=lambda item: (-item[1], item[0]))[:5]],
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "character_count": len(text),
    }
