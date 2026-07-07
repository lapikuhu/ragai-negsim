import json
from pydantic import BaseModel, Field
from typing import Any, Literal
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
import re

# local imports
from app.airag.prompts.sys_prompts import DOC_GRADE_PROMPT, REWRITE_PROMPT, GEN_PROMPT
from app.airag.prompts.sys_prompts import HALL_PROMPT, ANS_GRADER_PROMPT, FALLBACK_PROMPT
from app.core.config import settings
from app.airag.embeddings.embeddings import choose_embedding_model
from app.airag.llm_models.llm_models import get_llm, get_openai_llm

OPENAI_API_KEY = settings.OPENAI_API_KEY
llm_model_name   = "gpt-4o-mini"
embedding_model_name = "text-embedding-3-small"

embeddings, dimensionality = choose_embedding_model(embedding_model_name)
llm = get_openai_llm(llm_model_name, temperature=0)

### --------- Helper functions for the nodes --------- ###

### ---------------------------------------------------------------- ###
### ------------------- Docs Formatter to string ------------------- ###
### ---------------------------------------------------------------- ###

def format_docs(documents: list[Document]) -> str:
    """Format a list of langchain Documents into a string representation 
    for grading.
    Args:
        documents (list[Document]): A list of langchain Document objects 
            to format.
    Returns:
        str: A formatted string representation of the documents.
    """
    if not documents:
        return ""
    return "\n\n".join(
        f"[{idx}] Source: {doc.metadata.get('source', 'unknown')}\n{doc.page_content}"
        for idx, doc in enumerate(documents, start=1)
    )
### ---------------------------------------------------------------- ###


def format_trusted_context_sections(sections: list[tuple[str, Any]]) -> str:
    """
    Format trusted non-retrieval evidence into labeled text blocks.
    Args:
        sections (list[tuple[str, Any]]): A list of tuples containing a 
            label and a value.
    Returns:
        str: A formatted string representation of the trusted context 
        sections.
    """
    blocks = []
    for label, value in sections:
        if value in (None, "", [], {}):
            continue
        if isinstance(value, str):
            rendered = value
        else:
            rendered = json.dumps(value, default=str, ensure_ascii=False, indent=2)
        blocks.append(f"{label}:\n{rendered}")
    return "\n\n".join(blocks)
### ---------------------------------------------------------------- ###

### ---------------------------------------------------------------- ###
### ------------------------ ANSWER GRADER ------------------------- ###
### ---------------------------------------------------------------- ###

class AnswerGrade(BaseModel):
    """Evaluate whether the answer actually addresses the user question."""
    addresses: Literal["yes", "no"] = Field(
        description="Does the answer address what the question asked?"
    )
answer_grader = ANS_GRADER_PROMPT | llm.with_structured_output(AnswerGrade)

### ---------------------------------------------------------------- ###

### ---------------------------------------------------------------- ###
### ----------------------- Document Grader ------------------------ ###
### ---------------------------------------------------------------- ###
class DocumentGrade(BaseModel):
    """
    Evaluate whether retrieved documents are useful for answering the question.
    """
    relevance: Literal["relevant", "not_relevant"] = Field(
        description="Whether the retrieved documents contain information useful for answering the question."
    )
    reasoning: str = Field(description="Brief explanation of the verdict")

document_grader = DOC_GRADE_PROMPT | llm.with_structured_output(DocumentGrade)
### ---------------------------------------------------------------- ###

### ---------------------------------------------------------------- ###
### --------------------- Hallucination Check ---------------------- ###
### ---------------------------------------------------------------- ###
class HallucinationGrade(BaseModel):
    """Evaluate whether all claims in an answer are grounded in available evidence."""
    grounded:  Literal["yes", "no"] = Field(description="Are all claims supported by the retrieved or trusted evidence?")
    reasoning: str                  = Field(description="Brief explanation of the verdict")

hallucination_grader = HALL_PROMPT | llm.with_structured_output(HallucinationGrade)
### ---------------------------------------------------------------- ###


### --------------------------- REWRITER --------------------------- ###
rewrite_chain = REWRITE_PROMPT | llm | StrOutputParser()

### --------------------------- GENERATOR -------------------------- ###
generation_chain = GEN_PROMPT | llm | StrOutputParser()

### --------------------------- FALLBACK -------------------------- ###
fallback_chain = FALLBACK_PROMPT | llm | StrOutputParser()


def make_crag_component_chains(selections: dict[str, dict[str, str]] | None = None) -> dict[str, object]:
    """
    Make a dictionary of CRAG component chains based on the provided selections.
    Args:
        selections (dict[str, dict[str, str]] | None): A dictionary mapping 
            component names to their respective provider and model selections.
    Returns:
        dict[str, object]: A dictionary mapping component names to their
            respective chains.
    """
    selections = selections or {}

    def component_llm(component: str):
        selection = selections.get(component, {})
        return get_llm(
            provider=selection.get("provider", "openai"),
            model_name=selection.get("model", llm_model_name),
            temperature=0,
        )

    document_llm = component_llm("document_grader")
    rewrite_llm = component_llm("rewrite")
    generate_llm = component_llm("generate")
    hallucination_llm = component_llm("hallucination_grader")
    answer_llm = component_llm("answer_grader")
    fallback_llm = component_llm("fallback")

    return {
        "document_grader": DOC_GRADE_PROMPT | document_llm.with_structured_output(DocumentGrade),
        "rewrite": REWRITE_PROMPT | rewrite_llm | StrOutputParser(),
        "generate": GEN_PROMPT | generate_llm | StrOutputParser(),
        "hallucination_grader": HALL_PROMPT | hallucination_llm.with_structured_output(HallucinationGrade),
        "answer_grader": ANS_GRADER_PROMPT | answer_llm.with_structured_output(AnswerGrade),
        "fallback": FALLBACK_PROMPT | fallback_llm | StrOutputParser(),
    }
### ---------------------------------------------------------------- ###
