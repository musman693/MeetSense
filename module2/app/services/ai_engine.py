import json
import openai
from app.config import settings
from app.core.date_parser import parse_natural_deadline

openai.api_key = settings.OPENAI_API_KEY

async def extract_meeting_insights(transcript_text: str, summary_type: str = "detailed") -> dict:
    summary_instruction = (
        "Provide a short executive summary (2-3 sentences max)."
        if summary_type == "short"
        else "Provide a comprehensive, detailed executive summary covering major discussion points."
    )

    prompt = f"""
    You are an expert AI Meeting Analysis Engine. Analyze the following meeting transcript.

    Instruction for Summary: {summary_instruction}

    Extract and return a valid JSON object with EXACTLY these keys:
    - summary: string
    - key_points: list of strings
    - decisions: list of strings
    - action_items: list of objects with fields "task", "assigned_to", "deadline_text"
    - unresolved_issues: list of strings

    Transcript:
    "{transcript_text}"
    """

    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )

    parsed = json.loads(response.choices[0].message.content)

    for item in parsed.get("action_items", []):
        raw_deadline = item.get("deadline_text", "")
        item["structured_deadline"] = parse_natural_deadline(raw_deadline)

    return parsed