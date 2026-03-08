import os
import json
from datetime import date
from dotenv import load_dotenv

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.db import SessionLocal
from app.services.llm_prep_service import gather_daily_ai_data
from app.services.llm_inference import call_vertex_key_ai
from app.utils.config import settings

def test_llm_pipeline():
    # Load .env variables
    load_dotenv()
    
    # Check key
    if not settings.vertex_api_key:
        print("ERROR: Please set VERTEX_API_KEY in .env file.")
        print("Ví dụ: VERTEX_API_KEY=vai-abcxyz123...")
        return

    print("--- 1. Testing Data Preparation ---")
    session = SessionLocal()
    try:
        # Mocking values for VNINDEX dataframe logic used in gather_daily_ai_data since we don't fetch full today
        # Thay vì lấy thực, mock 1 dataframe nhỏ để bypass
        import pandas as pd
        mock_vni = pd.DataFrame([
            {"close": 1250.0},
            {"close": 1260.5}
        ])
        
        # Test gather payload (Target date: Lấy ngày có dữ liệu gần nhất trong DB)
        latest_date_row = session.execute(text("SELECT MAX(date) FROM stock_scores")).scalar()
        if not latest_date_row:
            print("Không tìm thấy dữ liệu scan trong DB.")
            return
            
        target_date = latest_date_row
        print(f"Gathering data for: {target_date}")
        
        payload = gather_daily_ai_data(
            session=session, 
            target_date=target_date, 
            market_regime="MARKUP", 
            vnindex_df=mock_vni, 
            breadth20_pct=65.5, 
            breadth50_pct=50.2
        )
        print("Payload prepared:")
        print(json.dumps(payload, indent=2, ensure_ascii=False))

        print("\n--- 2. Testing AI Inference ---")
        print(f"Calling Vertex-Key API với model: {settings.ai_model}")
        
        system_prompt = "Bạn là chuyên gia phân tích dữ liệu chứng khoán. Hãy nhận xét ngắn về payload."
        
        # Uncomment in real test to actually spend credits
        # response = call_vertex_key_ai(system_prompt, payload)
        # print("AI Response:")
        # print(json.dumps(response, indent=2, ensure_ascii=False))
        print("Thành công: Data Pipeline sẵn sàng gọi API.")

    except Exception as e:
        print(f"Test Failed: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    from sqlalchemy import text # import for raw sql
    test_llm_pipeline()
