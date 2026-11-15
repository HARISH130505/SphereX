"""
Research assistant and literature routes.
"""
from fastapi import APIRouter
from pydantic import BaseModel
from app.services.research.assistant import answer_research_inquiry

router = APIRouter(prefix="/research", tags=["Research"])

class ResearchRequest(BaseModel):
    question: str
    context_target: str = "M101"

@router.post("/ask")
def ask_assistant(req: ResearchRequest):
    return answer_research_inquiry(req.question, req.context_target)

@router.get("/briefing")
def get_briefing():
    return answer_research_inquiry("What are the key scientific capabilities of SPHEREx?")
