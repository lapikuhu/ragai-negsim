from pydantic import BaseModel, Field
from typing import Literal
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
import re

# local imports
from app.airag.prompts.sys_prompts import DOC_GRADE_PROMPT, REWRITE_PROMPT, GEN_PROMPT
from app.airag.prompts.sys_prompts import HALL_PROMPT, ANS_GRADER_PROMPT, FALLBACK_PROMPT
from app.core.config import settings
from app.airag.embeddings.embeddings import choose_embedding_model
from app.airag.llm_models.llm_models import get_openai_llm

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
    """Evaluate whether all claims in an answer are grounded in the context."""
    grounded:  Literal["yes", "no"] = Field(description="Are all claims supported by the context?")
    reasoning: str                  = Field(description="Brief explanation of the verdict")

hallucination_grader = HALL_PROMPT | llm.with_structured_output(HallucinationGrade)
### ---------------------------------------------------------------- ###


### --------------------------- REWRITER --------------------------- ###
rewrite_chain = REWRITE_PROMPT | llm | StrOutputParser()

### --------------------------- GENERATOR -------------------------- ###
generation_chain = GEN_PROMPT | llm | StrOutputParser()

### --------------------------- FALLBACK -------------------------- ###
fallback_chain = FALLBACK_PROMPT | llm | StrOutputParser()
### ---------------------------------------------------------------- ###
### ------------------ Prompt Injection Detection ------------------ ###
### ---------------------------------------------------------------- ###

INJECTION_PATTERNS = [
    r"ignore\s+(?:all\s+)?previous\s+instructions",
    r"reveal\s+(?:the\s+)?system\s+prompt",
    r"you\s+are\s+now\s+",
    r"pretend\s+(?:to\s+be|you\s+are)",
    r"forget\s+(?:all\s+)?(?:your\s+)?instructions",
    r"disregard\s+(?:all\s+)?(?:previous\s+)?instructions",
]

def detect_injection(text: str) -> bool:
    """Return True if the text contains a prompt injection pattern."""
    return any(re.search(p, text, re.IGNORECASE) for p in INJECTION_PATTERNS)

### ---------------------------------------------------------------- ###