import openai
import json
from app.config import settings

openai.api_key = settings.OPENAI_API_KEY

MEETING_VECTOR_STORE = {}

def index_meeting_chunks(meeting_id: str, chunks: list):
    MEETING_VECTOR_STORE[meeting_id] = chunks
    return len(chunks)

async def answer_meeting_question(meeting_id: str, question: str) -> dict:
    chunks = MEETING_VECTOR_STORE.get(meeting_id, [])
    
    if chunks:
        context_str = "\n".join([f"[{c.get('timestamp', '00:00')}] {c.get('speaker', 'Unknown')}: {c.get('text', '')}" for c in chunks])
        fallback_ts = chunks[0].get("timestamp", "00:00")
    else:
        context_str = "No specific indexed chunks found for this meeting."
        fallback_ts = "00:00"

    prompt = f"""
    You are a Meeting Q&A AI. Answer the question based ONLY on the provided transcript context.
    Always mention the timestamp where this answer originates from.

    Context:
    {context_str}

    Question: {question}

    Return JSON with fields:
    - answer: clear textual answer
    - timestamp_reference: timestamp string (e.g. '12:45')
    """

    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )

    res_data = json.loads(response.choices[0].message.content)
    
    return {
        "meeting_id": meeting_id,
        "question": question,
        "answer": res_data.get("answer", "Information not found in meeting."),
        "timestamp_reference": res_data.get("timestamp_reference", fallback_ts)
    }