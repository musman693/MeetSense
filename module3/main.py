from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import time
from app.routers import auth, dashboard

app = FastAPI(
    title="MeetSense - Module 3 Core Infrastructure API",
    version="1.0.0",
    description="Auth, PostgreSQL Schema, Vector Gateway, & Dashboard APIs"
)

# Shared Rate Limiting & Logging Middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["Dashboard Core Infrastructure"])

@app.get("/")
def health_check():
    return {"status": "active", "service": "MeetSense Module 3 Gateway Running"}