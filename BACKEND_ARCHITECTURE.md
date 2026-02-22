# Backend Architecture

## Folder Structure

backend/
│
├── app/
│   ├── main.py
│   ├── api/
│   ├── services/
│   ├── models/
│   ├── ml/
│   ├── pipeline/
│   ├── scheduler/
│   └── utils/
│
├── requirements.txt
└── run.py

---

## Core Modules

1. data_service.py
   - Fetch OHLCV data
   - Store raw data

2. feature_service.py
   - Calculate RSI, MACD, ATR, MA, Volume ratio

3. regime_service.py
   - HMM on VNINDEX
   - Detect 4 market states

4. scoring_service.py
   - Apply Vietnam cycle logic
   - Generate confidence score

5. scheduler.py
   - Run pipeline daily 18:30