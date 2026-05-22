from langchain_core.prompts import ChatPromptTemplate

DOC_GRADE_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are a strict document relevance grader for a Datanous.ai RAG system. "
     "Return 'relevant' only if the context contains information that can help answer the question. "
     "If the context is empty or unrelated, return 'not_relevant'."),
    ("human", "Question:\n{question}\n\nRetrieved context:\n{context}"),
])

REWRITE_PROMPT = ChatPromptTemplate.from_template( 
    "The original question did not return relevant results from the vector store. "
    "Rephrase it using different terminology that may better match the available content. "
    "Return only the rewritten question, no explanation.\n\n"
    "Original question: {question}\n\n"
    "Rewritten question:"
)

GEN_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are a precise RAG assistant. Answer only from the provided context. "
     "If the context does not contain the answer, say that the knowledge base does not contain enough information. "
     "Keep the answer concise and factual."),
    ("human", "Question:\n{question}\n\nContext:\n{context}\n\nAnswer:"),
])