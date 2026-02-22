# Vietnam Stock Cycle Scanner

## Objective

Build a fullstack system to:

1. Scan Vietnam stock market daily
2. Detect market regime (Accumulation / Markup / Distribution / Markdown)
3. Score stocks using volume-price cycle logic
4. Expose REST API
5. Display dashboard via VueJS frontend

---

## Tech Stack

Backend:
- Python 3.11
- FastAPI
- SQLAlchemy
- PostgreSQL or SQLite
- XGBoost
- hmmlearn
- APScheduler
- Pandas / NumPy

Frontend:
- Vue 3 (Composition API)
- Vite
- TailwindCSS
- ECharts
- Axios

---

## System Architecture

Frontend (Vue)
        ↓
FastAPI Backend
        ↓
Database
        ↓
Daily Scheduler (APScheduler)