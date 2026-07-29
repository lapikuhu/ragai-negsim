from types import SimpleNamespace


def test_persisted_chunk_conversion_preserves_dense_metadata_and_vector_references():
    from app.services.corpus_index_build_service import to_vector_documents

    chunks = [
        SimpleNamespace(
            id=41,
            raw_document_id=7,
            content="first chunk",
            chunk_metadata={"source": "course.pdf"},
        )
    ]

    documents, vector_refs = to_vector_documents(
        chunks=chunks,
        corpus_id=11,
        corpus_index_id=22,
        chunking_profile_id=3,
    )

    assert documents[0].page_content == "first chunk"
    assert documents[0].metadata == {
        "source": "course.pdf",
        "corpus_id": 11,
        "corpus_index_id": 22,
        "raw_document_id": 7,
        "chunking_profile_id": 3,
        "document_chunk_id": 41,
    }
    assert vector_refs[0].document_chunk_id == 41
    assert vector_refs[0].external_vector_id == "corpus-index-22-chunk-41"
