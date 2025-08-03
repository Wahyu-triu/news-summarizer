from pydantic import BaseModel

class ChatRequest(BaseModel):
    # session_id: str  # Use a unique ID per user/session
    question: str