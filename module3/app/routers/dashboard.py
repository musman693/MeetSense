from fastapi import APIRouter, Depends
from typing import List
from app.schemas.dashboard import DashboardSummary, RecentMeetingSchema
from app.core.security import get_current_user

router = APIRouter()

@router.get("/stats", response_model=DashboardSummary)
async def get_dashboard_stats(current_user: dict = Depends(get_current_user)):
    return {
        "total_meetings": 14,
        "processing_count": 1,
        "total_action_items": 28,
        "pending_decisions": 6,
        "upcoming_deadlines_count": 4
    }

@router.get("/recent-meetings", response_model=List[RecentMeetingSchema])
async def get_recent_meetings(current_user: dict = Depends(get_current_user)):
    return [
        {
            "id": "m_101",
            "title": "Q3 Product Roadmap Review",
            "status": "completed",
            "duration_seconds": 1840,
            "created_at": "2026-08-25T10:00:00Z"
        },
        {
            "id": "m_102",
            "title": "Marketing Sprint Planning",
            "status": "processing",
            "duration_seconds": 1200,
            "created_at": "2026-08-28T14:30:00Z"
        }
    ]