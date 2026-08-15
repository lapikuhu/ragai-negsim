from app.repositories.corpus_chunk_sets_repo import document_chunk_ids_checksum


def test_document_chunk_ids_checksum_is_order_independent():
    assert document_chunk_ids_checksum([13, 11]) == document_chunk_ids_checksum([11, 13])
