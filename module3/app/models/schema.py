from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from pgvector.sqlalchemy import Vector
from app.core.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class Meeting(Base):
    __tablename__ = "meetings"
    id = Column(String, primary_primary=True, index=True)
    title = Column(String, index=True)
    status = Column(String, default="processing")  # processing, completed, failed
    duration_seconds = Column(Integer, default=0)
    file_url = Column(String)
    owner_id = Column(String, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    transcripts = relationship("Transcript", back_populates="meeting")
    action_items = relationship("ActionItem", back_populates="meeting")
    decisions = relationship("Decision", back_populates="meeting")

class Transcript(Base):
    __tablename__ = "transcripts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    meeting_id = Column(String, ForeignKey("meetings.id"))
    speaker = Column(String)
    timestamp = Column(String)
    text = Column(Text)
    embedding = Column(Vector(1536), nullable=True)  # Vector embedding for retrieval

    meeting = relationship("Meeting", back_populates="transcripts")

class ActionItem(Base):
    __tablename__ = "action_items"
    id = Column(Integer, primary_key=True, autoincrement=True)
    meeting_id = Column(String, ForeignKey("meetings.id"))
    task = Column(Text, nullable=False)
    assigned_to = Column(String)
    deadline = Column(String)
    is_completed = Column(Integer, default=0)

    meeting = relationship("Meeting", back_populates="action_items")

class Decision(Base):
    __tablename__ = "decisions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    meeting_id = Column(String, ForeignKey("meetings.id"))
    decision_text = Column(Text, nullable=False)

    meeting = relationship("Meeting", back_populates="decisions")