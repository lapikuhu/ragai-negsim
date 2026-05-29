import os
from pathlib import Path
from docling.document_converter import DocumentConverter
from pypdf import PdfReader
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption, ConversionResult
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend

# local imports
from core.config import settings

# Set up the corpus directory path using the configuration from settings
corpus_dir = Path(settings.RAW_DOCS_DIR)


# Set-up the pipeline options for PDF processing
# These options will increase speed to about 1 sec per page for a typical PDF
pdf_pipeline_options = PdfPipelineOptions()
pdf_pipeline_options.do_ocr = False
# Keep table structure in the output
pdf_pipeline_options.do_table_structure = True
pdf_pipeline_options.force_backend_text = True
# Do not screenshot pdf pages
pdf_pipeline_options.generate_page_images = False
# Do not generate images for detected pictures
pdf_pipeline_options.generate_picture_images = False

fast_document_converter = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfFormatOption(
            pipeline_options=pdf_pipeline_options,
            backend=PyPdfiumDocumentBackend,
        )
    }
)


def ingest_pdfs_from_corpus(corpus_dir: Path, 
                            document_converter: DocumentConverter = fast_document_converter) -> list[ConversionResult]:
    """Ingest PDF documents from the specified corpus directory.
    Args:
        corpus_dir (Path): The path to the directory containing PDF documents.
        document_converter (DocumentConverter): The document converter instance to use for conversion.
    Returns:
        list[ConversionResult]: A list of ingested documents in the 
        internal Docling format.   
    """
    documents = []
    for pdf_file in corpus_dir.glob("*.pdf"):
        print(f"Ingesting {pdf_file}...")
        try:
            doc = document_converter.convert(pdf_file)
            documents.append(doc)
            print(f"Successfully ingested {pdf_file}")
        except Exception as e:
            print(f"Error ingesting {pdf_file}: {e}")
    return documents

def ingest_single_pdf(pdf_path: Path, document_converter: DocumentConverter = fast_document_converter) -> ConversionResult:
    """Ingest a single PDF document from the specified path.
    Args:
        pdf_path (Path): The path to the PDF document to ingest.
        document_converter (DocumentConverter): The document converter instance to use for conversion.
    Returns:
        ConversionResult: The ingested document in the internal Docling format.   
    """
    try:
        print(f"Ingesting {pdf_path}...")
        doc = document_converter.convert(pdf_path)
        print(f"Successfully ingested {pdf_path}")
        return doc
    except Exception as e:
        print(f"Error ingesting {pdf_path}: {e}")
        raise e

def convert_to_markdown(document: ConversionResult) -> str:
    """Convert docling ingested document to markdown format.
    Works only for docling ingested documents.
    Args:
        document (ConversionResult): The docling ingested document to convert.
    Returns:
        str: The converted document in markdown format.   
    """
    conversion_result = document.document.export_to_markdown(
        image_placeholder="",  # No placeholder for images since we are not generating them in the pipeline options
    )
    return conversion_result
