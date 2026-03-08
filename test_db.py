import sys
import os
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
sys.path.append(os.path.dirname(os.path.abspath(__name__)))

from app.services import llm_prep_service
from app.utils.config import settings
import pandas as pd

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

session = SessionLocal()
target_date = date(2026, 3, 6)

try:
    print("Testing SQL gather_daily_ai_data...")
    vni_df = pd.DataFrame([{"close": 1200, "date": target_date}])
    res = llm_prep_service.gather_daily_ai_data(session, target_date, "ACCUMULATION", vni_df, 50.0, 40.0)
    print("User Portfolio data:")
    print(res.get("Danh mục Đầu tư Đang nắm giữ"))
    print("SUCCESS.")
except Exception as e:
    import traceback
    traceback.print_exc()
finally:
    session.close()
