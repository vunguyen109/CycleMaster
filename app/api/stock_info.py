import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from app.models.db import SessionLocal
from app.models.schemas import CompanyOut, OHLCVOut
import pandas as pd
from datetime import date

logger = logging.getLogger(__name__)

router = APIRouter()

def get_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get('/companies', response_model=List[CompanyOut])
def get_companies(session=Depends(get_session)):
    """
    Fetch the list of all companies from the local database.
    """
    try:
        from app.models.models import Stock
        stocks = session.query(Stock).all()
        result = []
        for stock in stocks:
            result.append(CompanyOut(
                ticker=stock.symbol,
                company_name=stock.symbol,
                company_short_name=stock.symbol,
                industry=stock.sector if stock.sector else 'Khác'
            ))
        return result
    except Exception as exc:
        logger.error(f"Error fetching companies from database: {exc}")
        raise HTTPException(status_code=500, detail="Failed to fetch company list")


@router.get('/history/{symbol}', response_model=List[OHLCVOut])
def get_stock_history(symbol: str, length: int = Query(500, description="Number of historical days to fetch")):
    """
    Fetch historical OHLCV data for a specific symbol using vnstock.
    """
    try:
        from vnstock import Quote
        quote = Quote(symbol=symbol.upper())
        df = quote.history(length=length, interval='1D')
        
        if df is None or df.empty:
            return []
            
        if 'time' in df.columns:
            df = df.rename(columns={'time': 'date'})
            
        result = []
        for _, row in df.iterrows():
            # Handle potential missing or invalid data safely
            try:
                date_val = pd.to_datetime(row['date']).date()
                result.append(OHLCVOut(
                    date=date_val,
                    open=float(row.get('open', 0)),
                    high=float(row.get('high', 0)),
                    low=float(row.get('low', 0)),
                    close=float(row.get('close', 0)),
                    volume=float(row.get('volume', 0)),
                    symbol=symbol.upper()
                ))
            except Exception as e:
                logger.debug(f"Row conversion error form symbol {symbol}: {e}")
                continue
                
        return result
    except Exception as exc:
        logger.error(f"Error fetching history for {symbol}: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch history for {symbol}")
