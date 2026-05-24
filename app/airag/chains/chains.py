from core.config import settings
from pathlib import Path
from langchain_core.documents import Document

# local imports
from core.config import settings

from ingestion.loaders import ingest_pdfs_from_corpus, ingest_single_pdf, convert_to_markdown, fast_document_converter
from ingestion.ingestion import clean_markdown, split_md_on_headers
from chunking.chunkers import chunk_document_list_semantic, chunk_document_list_recursive
from embeddings.embeddings import choose_embedding_model

### ------ Development chains for manual testing and sanity checks -------- ###

# Set the embeddings model
OPENAI_API_KEY = settings.OPENAI_API_KEY
EMBED_MODEL = "text-embedding-3-small"
embeddings, dimensionality = choose_embedding_model(EMBED_MODEL)

# Define the documents to load
documents =["example_1.pdf",
"example_2.pdf"]
# Load the document (single PDF line for testing)
loaded_doc = ingest_single_pdf(Path(settings.RAW_DOCS_DIR) / documents[0], fast_document_converter)
# Convert to markdown
markdown_content = convert_to_markdown(loaded_doc)
# Clean the markdown content
cleaned_markdown = clean_markdown(markdown_content, convert_to_langDoc=True, source=documents[0])
# Dynamically chunk the cleaned markdown based on headers
chunked_sections = split_md_on_headers(cleaned_markdown, 
                                        header_depth=2, 
                                        dynamic_length=True, 
                                        size_threshold=12000, 
                                        min_length=1000)
# Semantically chunk the cleaned markdown content
semantic_chunks = chunk_document_list_semantic(chunked_sections,
                                               embeddings=embeddings,
                                               breakpoint_threshold_type="percentile",
                                               breakpoint_threshold_amount=90,
                                               buffer_size=1)

# Finally chunk document recursively with character-based chunking
final_chunks = chunk_document_list_recursive(semantic_chunks,
                                             chunk_size=1000,
                                             chunk_overlap=200,
                                             separators=["\n\n", "\n", " ", ""])