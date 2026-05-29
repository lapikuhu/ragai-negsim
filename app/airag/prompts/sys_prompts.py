from langchain_core.prompts import ChatPromptTemplate

DOC_GRADE_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are a strict document relevance grader for a RAG system. "
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

FAITHFULNESS_PROMPT = ChatPromptTemplate.from_template(
    "You are a strict evaluator. Given a context and an answer, score how well "
    "ALL claims in the answer are supported by the context.\n"
    "Return only a number from 0.0 (no support) to 1.0 (fully supported).\n\n"
    "Context:\n{context}\n\nAnswer:\n{answer}\n\nScore (0-1):"
)

ANS_RELEVANCY_PROMPT = ChatPromptTemplate.from_template(
    "How relevant is the answer to the question?\n"
    "Return only a number from 0.0 (irrelevant) to 1.0 (fully relevant).\n\n"
    "Question:\n{question}\n\nAnswer:\n{answer}\n\nScore (0-1):"
)

ANS_GRADER_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "Evaluate whether the answer actually addresses the user question. "
     "Return 'yes' if it does, 'no' otherwise. Do not return an explanation, just 'yes' or 'no'. "),
    ("human", "Question: {question}\n\nAnswer: {answer}"),
])

HALL_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "Check whether ALL claims in the answer are supported by the context. "
     "If the answer contains any claim not found in the context, return 'no'."),
    ("human", "Context:\n{context}\n\nAnswer:\n{answer}"),
])

FALLBACK_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are a helpful assistant in a Corrective RAG system. "
     "The retrieval step did not find relevant information in the knowledge base, "
     "and no web search is available or allowed. "
     "Answer using only your general model training. "
     "You must explicitly tell the user that nothing relevant was found in the knowledge base "
     "and that the answer relies on the model's general training. "
     "Do not pretend that the answer is sourced from the knowledge base. "
     "Be concise, cautious, and avoid fabricating citations or sources."),
    ("human",
     "User question:\n{question}\n\n"
     "Final attempted query, if rewritten:\n{rewritten}\n\n"
     "Answer:")
])