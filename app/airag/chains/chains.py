from core.config import settings
from pathlib import Path
from ingestion.loaders import ingest_pdfs_from_corpus, ingest_single_pdf, convert_to_markdown, fast_document_converter
from ingestion.ingestion import clean_markdown, split_md_on_headers

# Load the document
loaded_doc = ingest_single_pdf(Path(settings.RAW_DOCS_DIR) / "example.pdf", fast_document_converter)
# Convert to markdown
markdown_content = convert_to_markdown(loaded_doc)
# Clean the markdown content
cleaned_markdown = clean_markdown(markdown_content)
# Dynamically chunk the cleaned markdown based on headers
chunked_sections = split_md_on_headers(cleaned_markdown, 
                                        header_depth=2, 
                                        dynamic_length=True, 
                                        size_threshold=12000, 
                                        min_length=1000)
# Semantically chunk the cleaned markdown content
