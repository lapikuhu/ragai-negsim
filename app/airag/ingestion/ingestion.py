from langchain_core.documents import Document
from langchain_docling import DoclingLoader
from langchain_docling.loader import ExportType
from pathlib import Path
import re

from langchain_text_splitters import MarkdownHeaderTextSplitter

HEADER_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")


def _is_header(line: str) -> tuple[bool, int | None]:
    """Check if a line is a Markdown header and return its level.
    Args:
        line (str): The line of text to check.
    Returns:
        tuple[bool, int | None]: A tuple where the first element is True if the 
        line is a header, and the second element is the header level if it is 
        a header, otherwise None.
    """
    match = HEADER_RE.match(line.strip())

    if not match:
        return False, None

    level = len(match.group(1))
    return True, level


def remove_dummy_markdown_headers(markdown: str) -> str:
    """
    Remove Markdown headers that have no body and no child subheader.

    A header is removed if the next meaningful line is:
    - a header of the same level,
    - a header of a higher parent level,
    - or the end of the document.

    A header is kept if the next meaningful line is:
    - normal content,
    - a lower-level subheader.
    """
    lines = markdown.splitlines()
    keep = [True] * len(lines)

    in_fence = False

    for i, line in enumerate(lines):
        if FENCE_RE.match(line):
            in_fence = not in_fence

        if in_fence:
            continue

        is_header, current_level = _is_header(line)

        if not is_header:
            continue

        # Find next meaningful non-empty line
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1

        # Header at the end of the document
        if j >= len(lines):
            keep[i] = False
            continue

        next_is_header, next_level = _is_header(lines[j])

        if not next_is_header:
            # Followed by real content
            keep[i] = True
            continue

        if next_level > current_level:
            # Followed by a child/subheader
            keep[i] = True
            continue

        # Followed by same-level or higher-level header
        # Therefore this header has no content and no children.
        keep[i] = False

    return "\n".join(
        line for line, should_keep in zip(lines, keep) if should_keep
    )

    
def clean_markdown(md_content: str,
                   convert_to_langDoc: bool = True,
                   source: str ="") -> str:
    """Clean markdown content by removing unnecessary whitespace and normalizing line breaks.
    Args:
        md_content (str): The markdown content to clean.
        convert_to_langDoc (bool, optional): Whether to convert the cleaned markdown to a LangChain Document. Defaults to True.
        source (str, optional): The source of the document, used for metadata if converting to LangChain Document. Defaults to an empty string.
    Returns:
        str: The cleaned markdown content.        
    """

    # Remove leading and trailing whitespace from each line and normalize line breaks
    cleaned_lines = [line.strip() for line in md_content.splitlines()]
    cleaned_md = "\n".join(cleaned_lines)

    # Collapse 3+ consecutive blank lines into 2
    cleaned_md = re.sub(r'\n{3,}', '\n\n', cleaned_md)

    # Fix missing space after heading markers
    cleaned_md = re.sub(r'^(#{1,6})([^#\s])', r'\1 \2', cleaned_md, flags=re.MULTILINE)

    # Remove stray page numbers (lines containing only digits)
    cleaned_md = re.sub(r'^\d+\s*$', '', cleaned_md, flags=re.MULTILINE)

    # Fix PDF hyphenation breaks
    cleaned_md = re.sub(r'-\n(\w)', r'\1', cleaned_md)

    # Normalize unicode quotes and dashes
    cleaned_md = cleaned_md.replace('\u201c', '"').replace('\u201d', '"')
    cleaned_md = cleaned_md.replace('\u2018', "'").replace('\u2019', "'")
    cleaned_md = cleaned_md.replace('\u2014', ' - ')

    # Remove dummy headers that have no content and no child subheaders
    cleaned_md = remove_dummy_markdown_headers(cleaned_md)
    # Optionally convert to langDoc format (if needed for downstream processing)
    if convert_to_langDoc:
        cleaned_md = Document(page_content=cleaned_md, metadata={"source": source})
    else:
        cleaned_md = cleaned_md
    return cleaned_md


def find_headers_stats(md_content: Document, header_depth: int=6):
    """Get basic statics about the headers in the markdown content, 
    such as minimum and maximum header lengths for each header level, as well as
    the average header length and the count of headers for each level.
    Args:
        md_content (Document): The markdown content to analyze.
        header_depth (int, optional): The depth of headers to analyze. For 
            example, a value of 2 will analyze headers up to "##". Defaults 
            to 6. Maximum supported header depth is 6 (i.e., up to "######").
    Returns:
        dict: A dictionary where the keys are header levels (e.g., "header_1")
        and the values are dictionaries containing the minimum and maximum header
        lengths, the count of headers, and the average header length for that 
        level. For example:
        {"header_1": {"min": 5, "max": 50, "count": 3, "avg_length": 20}, 
        "header_2": {"min": 3, "max": 30, "count": 2, "avg_length": 15}, ...}   
    """
    # Extract md from docling Document if needed
    if isinstance(md_content, Document):
        md_content = md_content.page_content
    
    if header_depth < 1 or header_depth > 6:
        raise ValueError("header_depth must be between 1 and 6")
    header_patterns = [(f"{'#' * i}", f"header_{i}") for i in range(1, header_depth + 1)]
    splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=header_patterns,
        strip_headers=True,  # We only want the content for stats, not the headers themselves
    )
    md_splits = splitter.split_text(md_content)
    header_lengths = {f"header_{i}": {"min": float("inf"), "max": 0, "count": 0, "total_length": 0, "avg_length": 0} for i in range(1, header_depth + 1)}
    for split in md_splits:
        header_level = split.metadata.get("header_level")
        if header_level:
            header_lengths[header_level]["min"] = min(header_lengths[header_level]["min"], len(split.page_content))
            header_lengths[header_level]["max"] = max(header_lengths[header_level]["max"], len(split.page_content))
            header_lengths[header_level]["count"] = header_lengths[header_level].get("count", 0) + 1
            # Find the total length of headers for this level
            total_length = header_lengths[header_level].get("total_length", 0) + len(split.page_content)
            header_lengths[header_level]["total_length"] = total_length
            # Get the average header length for this level
            header_lengths[header_level]["avg_length"] = total_length / header_lengths[header_level]["count"]
    return header_lengths


def split_md_on_headers(md_content: Document, 
                        header_depth: int=2,
                        dynamic_length: bool = False,
                        size_threshold: int = 12000,
                        min_length: int = 12000) -> list[Document]:
    """Split markdown content into sections based on header levels. Wrapper of
    MarkdownHeaderTextSplitter. Depth can be user defined or dynamically 
    determined based on the content. If dynamic, the meat of the function 
    (MarkdownHeaderTextSplitter) will be called twice, once for analysis,
    and once for the actual splitting.
    Assumes roughly 4 chars per token, so a size threshold of 12000 chars 
    corresponds to about 3000 tokens. This default allows downstream chunkers
    to have enough context to work with, while still splitting on meaningful
    sections of the document.
    Args:
        md_content (Document): The markdown content to split.
        header_depth (int, optional): The depth of headers to split on. For 
            example, a value of 2 will split on headers up to "##". Defaults 
            to 2. Maximum supported header depth is 6 (i.e., up to "######").
        dynamic_length (bool, optional): Whether to use dynamic header lengths
            for splitting. Defaults to False. If True, the function will analyze
            the markdown content to find the optimal header lengths for splitting.
        size_threshold (int, optional): The size threshold doing any splitting.
            If the markdown content is smaller than this threshold, it will not
            be split, regardless of the header structure. Defaults to 12000.
        min_length (int, optional): The minimum length of a section before splitting.
    Returns:
        list[Document]: A list of langchain Document sections split based on headers.   
    """

    # Extract md from docling Document
    if isinstance(md_content, Document):
        metadata = md_content.metadata
        md_content = md_content.page_content

    if (header_depth < 1 or header_depth > 6) and not dynamic_length:
        raise ValueError("header_depth must be between 1 and 6")
    
     # Sanity check: Skip splitting if the content is too short, let the chunker
    # handle it instead
    if len(md_content) < size_threshold:
        print(f"Content is smaller than size threshold ({size_threshold} chars), skipping header splitting.")
        return [Document(page_content=md_content, metadata=metadata)]
       
    # Create header patterns based on the specified header depth
    header_patterns = [(f"{'#' * i}", f"header_{i}") for i in range(1, header_depth + 1)]

    # Dynamically split on headers based on the content analysis
    if dynamic_length:
        header_stats = find_headers_stats(md_content, header_depth=6)
        # Find the header level with the highest average length that is below the size threshold
        optimal_header_level = None
        for header_level, stats in header_stats.items():
            if stats["avg_length"] > min_length: # More than the minimum length, can be split on this header level
                if optimal_header_level is None or stats["avg_length"] > header_stats[optimal_header_level]["avg_length"]:
                    optimal_header_level = header_level
        if optimal_header_level is not None:
            # Update the header patterns to split on the optimal header level
            header_index = int(optimal_header_level.split("_")[1])
            header_patterns = [(f"{'#' * i}", f"header_{i}") for i in range(1, header_index + 1)]
        else:
            # If no optimal header level is found, fallback to the specified header depth
            header_patterns = [(f"{'#' * i}", f"header_{i}") for i in range(1, header_depth + 1)]
    else:   
        # If not using dynamic length, just use the specified header depth
        header_patterns = [(f"{'#' * i}", f"header_{i}") for i in range(1, header_depth + 1)]

    splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=header_patterns,
        strip_headers=False,  # Include headers in the splits to preserve context
    )

    splits = []

    md_splits = splitter.split_text(md_content)

    for split in md_splits:
        # Preserve original file-level metadata
        split.metadata.update(metadata)
        splits.append(split)
    
    return splits