from langchain_core.prompts import ChatPromptTemplate

# TODO: Reframe the prompts following the PCTF format
DOC_GRADE_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are a document relevance grader for a RAG system that combines "
     "retrieved knowledge with separate scenario facts. "
     "Evaluate whether the retrieved context contains at least one materially "
     "useful concept that can improve the answer. "
     "Transferable theory, tactics, frameworks, definitions, or decision "
     "criteria count as relevant even when they are not scenario-specific. "
     "For negotiation questions, applicable concepts may include ZOPA, "
     "reservation values, BATNA, anchoring, concessions, package terms, "
     "questioning tactics, and deal evaluation. "
     "Do not require the context to mention the same scenario, actors, domain "
     "terms, or numeric values as the question. "
     "A single materially useful concept is sufficient for 'relevant'. "
     "Return 'not_relevant' only when the context is empty, belongs to an "
     "unrelated domain, or is too vague to improve the answer. "
     "In the reasoning, identify the applicable concept or briefly explain "
     "why no useful concept applies."),
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
     "You are a precise RAG assistant. Answer only from the provided retrieved context and trusted simulation context. "
     "Treat both as authoritative evidence, and do not introduce facts from outside them. "
     "If neither source contains enough information, say that the available evidence does not contain enough information. "
     "Keep the answer concise and factual."),
    ("human", "Question:\n{question}\n\nRetrieved context:\n{context}\n\nTrusted simulation context:\n{trusted_context}\n\nAnswer:"),
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
     "Check whether the answer's material factual claims are supported by the available evidence. "
     "The retrieved context and trusted simulation context are both authoritative evidence sources. "
     "Allow clear deductions such as arithmetic, direct comparisons, and standard negotiation conclusions when their premises are supported. "
     "Do not require verbatim matches. "
     "If the answer invents scenario facts, changes supported numbers, or makes material claims not supported by either evidence source, return 'no'."),
    ("human", "Retrieved context:\n{context}\n\nTrusted simulation context:\n{trusted_context}\n\nAnswer:\n{answer}"),
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
