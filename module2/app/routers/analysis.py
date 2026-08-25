from fastapi import APIRouter, HTTPException
from app.schemas.analysis import (
    AnalysisRequest, 
    AnalysisResponse, 
    IndexTranscriptRequest, 
    QAQueryRequest, 
    QAResponse
)
from app.services.ai_engine import extract_meeting_insights
from app.services.vector_service import index_meeting_chunks, answer_meeting_question

router = APIRouter()

@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_meeting(payload: AnalysisRequest):
    if payload.summary_type not in ["short", "detailed"]:
        raise HTTPException(status_code=400, detail="summary_type must be 'short' or 'detailed'")

    insights = await extract_meeting_insights(payload.transcript, payload.summary_type)
    
    return {
        "meeting_id": payload.meeting_id,
        "summary": insights.get("summary", ""),
        "key_points": insights.get("key_points", []),
        "decisions": insights.get("decisions", []),
        "action_items": insights.get("action_items", []),
        "unresolved_issues": insights.get("unresolved_issues", [])
    }

@router.post("/index-transcript")
async def index_transcript(payload: IndexTranscriptRequest):
    count = index_meeting_chunks(payload.meeting_id, payload.transcript_chunks)
    return {"status": "success", "indexed_chunks": count}

@router.post("/qa", response_model=QAResponse)
async def meeting_qa(payload: QAQueryRequest):
    result = await answer_meeting_question(payload.meeting_id, payload.question)
    return result