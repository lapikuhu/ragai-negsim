from langchain_openai import ChatOpenAI
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from typing import TypedDict, Literal
from langgraph.graph import StateGraph, START, END
try:
    from typing import NotRequired
except ImportError:
    from typing_extensions import NotRequired
from pydantic import BaseModel, Field

# local imports
from core.config import settings
from prompts.sys_prompts import DOC_GRADE_PROMPT, REWRITE_PROMPT, GEN_PROMPT

OPENAI_API_KEY = settings.OPENAI_API_KEY
LLM_MODEL   = "gpt-4o-mini"
EMBED_MODEL = "text-embedding-3-small"
llm = ChatOpenAI(model=LLM_MODEL, temperature=0)

# Define the RAGState TypedDict to represent the state of the RAG process
class RAGState(TypedDict):
    question: str
    attempts: int
    rewritten: NotRequired[str]
    documents: NotRequired[list[Document]]
    answer: NotRequired[str]
    grade: NotRequired[str]
    context: NotRequired[str]
    hallucination_grade: NotRequired[str]
    answer_grade: NotRequired[str]
    quality_reasoning: NotRequired[str]

### --------- Helper functions for the nodes --------- ###
# Docs formatter for grading
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

class DocumentGrade(BaseModel):
    """Evaluate whether retrieved documents are useful for answering the question."""
    relevance: Literal["relevant", "not_relevant"] = Field(
        description="Whether the retrieved documents contain information useful for answering the question."
    )
    reasoning: str = Field(description="Brief explanation of the verdict")

document_grader = DOC_GRADE_PROMPT | llm.with_structured_output(DocumentGrade)

rewrite_chain = REWRITE_PROMPT | llm | StrOutputParser()

generation_chain = GEN_PROMPT | llm | StrOutputParser()

# Define the node functions for the RAG graph
# RETRIEVE
def node_retrieve(retriever,
                  state: RAGState) -> dict:
    """Define the retrieve node which takes the current question (original or 
        rewritten) and retrieves relevant documents from the vector store 
        retriever.
    Args:
        retriever: The retriever instance to use for retrieving relevant 
            documents based on the query.
        state: The current RAG state containing the question and any 
            rewritten versions.
    Returns:
        A dictionary containing the retrieved documents.
    """
    query = state.get("rewritten") or state["question"]
    docs = retriever.invoke(query)
    print(f"[retrieve] query={query!r} | docs={len(docs)}")
    return {"documents": docs}

# GRADE
def node_grade(state: RAGState) -> dict:
    """
    Define the grade node which evaluates the relevance of the retrieved 
    documents to the question.
    """
    docs = state.get("documents", [])
    if not docs:
        print("[grade] no documents retrieved → not_relevant")
        return {"grade": "not_relevant"}
    question = state.get("rewritten") or state["question"]
    context = format_docs(docs)
    verdict = document_grader.invoke({"question": question, "context": context})
    print(f"[grade] {verdict.relevance} | {verdict.reasoning}")
    return {"grade": verdict.relevance}

# REWRITE
def node_rewrite(state: RAGState) -> dict:
    """
    Define the rewrite node which attempts to reformulate the question if 
    the retrieved documents were not relevant.
    Args:
        state: The current RAG state containing the original question and any 
            previous rewritten versions.
    Returns:
        A dictionary containing the rewritten question and the number of
            rewrite attempts.
    """
    rewritten = rewrite_chain.invoke({"question": state["question"]}).strip()
    attempts = state.get("attempts", 0) + 1
    print(f"[rewrite] attempt={attempts} | rewritten={rewritten!r}")
    return {"rewritten": rewritten, "attempts": attempts}

# GENERATE
def node_generate(state: RAGState) -> dict:
    """
    Define the generate node which produces an answer based on the 
    retrieved documents.
    Args:
        state: The current RAG state containing the question and retrieved
            documents.
    Returns:
        A dictionary containing the generated answer and the context used for 
            generation.
    """
    docs = state.get("documents", [])
    context = format_docs(docs)
    answer = generation_chain.invoke({
        "question": state["question"],
        "context": context,
    }).strip()
    print("[generate] answer generated")
    return {"answer": answer, "context": context}

# FALLBACK
def node_fallback(state: RAGState) -> dict:
    """
    Define the fallback node which is invoked when the retrieved documents 
    are not relevant and we've exhausted rewrite attempts.
    """
    pass

### --------- Define graph routing logic --------- ###
def decide_after_grade(state: RAGState) -> str:
    if state.get("grade") == "relevant":
        return "generate"
    if state.get("attempts", 0) < MAX_ATTEMPTS:
        return "rewrite"
    return "fallback"

### --------- Build the RAG graph --------- ###
crag_flow = StateGraph(RAGState)
# Add nodes
crag_flow.add_node("retrieve",  node_retrieve)
crag_flow.add_node("grade",     node_grade)
crag_flow.add_node("rewrite",   node_rewrite)
crag_flow.add_node("generate",  node_generate)
crag_flow.add_node("fallback",  node_fallback)

# Edges
crag_flow.add_edge(START, "retrieve")
crag_flow.add_edge("retrieve", "grade")
crag_flow.add_conditional_edges(
    "grade",
    decide_after_grade,
    {"generate": "generate", "rewrite": "rewrite", "fallback": "fallback"},
)
crag_flow.add_edge("rewrite", "retrieve")   # retry loop
crag_flow.add_edge("generate", END)
crag_flow.add_edge("fallback", END)

crag = crag_flow.compile()