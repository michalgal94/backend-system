from processor_service.app.analyzer import analyze_document


def test_analyze_document_calculates_required_metadata() -> None:
    result = analyze_document("doc-1", "Hello hello world, document world.")
    assert result["word_count"] == 5
    assert result["unique_word_count"] == 3
    assert result["top_words"] == [{"word": "hello", "count": 2}, {"word": "world", "count": 2}, {"word": "document", "count": 1}]
    assert result["sha256"] == "6cced8a3bc4d82d78858c524d0049ac9e223e8d9cb2fa8b5beae9cc6293090ca"


def test_analyze_document_handles_no_words() -> None:
    result = analyze_document("empty", "!!!")
    assert result["word_count"] == 0
    assert result["unique_word_count"] == 0
    assert result["top_words"] == []
