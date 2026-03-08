import json
import logging
from typing import Dict, Any
from openai import OpenAI
from app.utils.config import settings

logger = logging.getLogger(__name__)

def call_vertex_key_ai(system_prompt: str, data_payload: dict, model_override: str = None) -> Dict[str, Any]:
    """
    Gọi API Vertex-Key (tương thích OpenAI) trả về JSON.
    Chỉ dùng 1 lần/ngày theo chiến lược Pay-as-you-go.
    """
    if not settings.vertex_api_key:
        logger.warning("Vertex API Key is not configured. Skipping AI Insights.")
        return {}

    model = model_override or settings.ai_model
    
    try:
        client = OpenAI(
            api_key=settings.vertex_api_key,
            base_url="https://vertex-key.com/api/v1"
        )
        
        prompt_text = f"{system_prompt}\n\n--- DỮ LIỆU ĐỊNH LƯỢNG HÔM NAY ---\n{json.dumps(data_payload, ensure_ascii=False, indent=2)}"
        
        logger.info(f"Calling Vertex-Key AI API (Model: {model})...")
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system", 
                    "content": "Bạn là chuyên gia đầu tư định lượng cấp độ Giám đốc Đầu tư (CIO). Chỉ trả lời duy nhất bằng định dạng JSON hợp lệ."
                },
                {
                    "role": "user", 
                    "content": prompt_text
                }
            ],
            temperature=0.2, # LLM suy luận phân tích nên để thấp
            max_tokens=2048,
            response_format={ "type": "json_object" }
        )
        
        content = response.choices[0].message.content
        logger.info(f"AI API Response: {content}")
        return json.loads(content)

    except Exception as e:
        logger.error(f"Error calling AI API: {e}", exc_info=True)
        return {"error": str(e)}
