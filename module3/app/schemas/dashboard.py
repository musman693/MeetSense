from pydantic import BaseModel, EmailStr
from typing import List, Optional

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str

class Token(BaseModel):
    access_token: str
    token_type: str

class DashboardSummary(BaseModel):
    total_meetings: int
    processing_count: int
    total_action_items: int
    pending_decisions: int
    upcoming_deadlines_count: int

class RecentMeetingSchema(BaseModel):
    id: str
    title: str
    status: str
    duration_seconds: int
    created_at: str