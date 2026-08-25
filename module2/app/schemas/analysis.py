from pydantic import BaseModel, Field
from typing import List, Optional

class AnalysisRequest(BaseModel):
    meeting_id: str
    transcript: str
    summary_type: Optional[str] = Field("detailed", description="Toggle between 'short' or 'detailed'")

class ActionItemSchema(BaseModel):
    task: str
    assigned_to: str
    deadline_text: str
    structured_deadline: str

class AnalysisResponse(BaseModel):
    meeting_id: str
    summary: str
    key_points: List[str]
    decisions: List[str]
    action_items: List[ActionItemSchema]
    unresolved_issues: List[str]

class IndexTranscriptRequest(BaseModel):
    meeting_id: str
    transcript_chunks: List[dict]

class QAQueryRequest(BaseModel):
    meeting_id: str
    question: str

class QAResponse(BaseModel):
    meeting_id: str
    question: str
    answer: str
    timestamp_reference: str