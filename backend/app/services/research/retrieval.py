"""
Information retrieval for research queries.
"""
from app.services.research.literature_search import search_literature

def retrieve_context(query: str) -> dict:
    answer = search_literature(query)
    return {"query": query, "context": answer}
