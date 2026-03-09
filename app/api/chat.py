from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import logging
from openai import OpenAI
from app.utils.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

class ChatMessage(BaseModel):
    role: str
    content: str
    
class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    model: str = "gpt-4o"

class ChatResponse(BaseModel):
    content: str

@router.post('/message', response_model=ChatResponse)
def send_chat_message(request: ChatRequest):
    """
    Send messages to the Vertex-Key AI API.
    """
    if not settings.vertex_api_key:
        logger.error("Vertex API Key is not configured for the chatbot.")
        raise HTTPException(status_code=500, detail="Chưa cấu hình API Key cho Chatbot.")

    try:
        client = OpenAI(
            api_key=settings.vertex_api_key,
            base_url="https://vertex-key.com/api/v1"
        )
        
        # Prepare messages format for OpenAI client
        formatted_messages = [
            {"role": "system", "content": "Bạn là chuyên gia cố vấn đầu tư chứng khoán thông minh, nhiệt tình. Tên của bạn là CycleMaster AI. Hãy trả lời ngắn gọn, súc tích, chuyên nghiệp và có định dạng dễ đọc."}
        ]
        
        for msg in request.messages:
            formatted_messages.append({
                "role": msg.role,
                "content": msg.content
            })
            
        logger.info(f"Calling Chat API (Model: {request.model}) with {len(formatted_messages)} messages.")
        
        response = client.chat.completions.create(
            model=request.model,
            messages=formatted_messages,
            temperature=0.7, 
            max_tokens=2048
        )
        
        content = response.choices[0].message.content
        return ChatResponse(content=content)

    except Exception as e:
        logger.error(f"Error calling Chat API: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
