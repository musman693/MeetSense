from fastapi import FastAPI
from app.routers import analysis

app = FastAPI(
    title="MeetSense - Module 2 AI Analysis Engine",
    version="1.0.0",
    description="Summarization, Action Items, Decisions, Deadlines, and Scoped Meeting Q&A"
)

app.include_router(analysis.router, prefix="/api/v1/analysis", tags=["Module 2 AI Analysis"])

@app.get("/")
def health_check():
    return {"status": "active", "service": "MeetSense Module 2 API"}