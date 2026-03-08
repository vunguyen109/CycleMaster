import logging
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import date
from app.models import models
from app.utils.config import settings
import feedparser

logger = logging.getLogger(__name__)

def gather_daily_ai_data(session: Session, target_date: date, market_regime: str, vnindex_df, breadth20_pct: float, breadth50_pct: float) -> dict:
    """
    Trích xuất dữ liệu định lượng của ngày hiện tại để gửi cho AI phân tích.
    Bao gồm: Chỉ số VNINDEX, Top ngành dẫn dắt, và Top 5 cổ phiếu đáng chú ý.
    """
    logger.info(f"Gathering AI insight data for {target_date}")
    
    # 1. Thông tin thị trường chung
    vni_last = vnindex_df.iloc[-1] if not vnindex_df.empty else None
    market_data = {
        "vnindex_close": float(vni_last['close']) if vni_last is not None else 0.0,
        "vnindex_change_pct": float(vni_last['close'] / vnindex_df.iloc[-2]['close'] - 1) * 100 if vni_last is not None and len(vnindex_df) > 1 else 0.0,
        "market_regime_hmm": market_regime,
        "breadth_above_ma20_pct": round(breadth20_pct, 1),
        "breadth_above_ma50_pct": round(breadth50_pct, 1)
    }

    # 2. Thông tin top cổ phiếu ngày hôm nay (Lọc điểm cao nhất)
    top_stocks = session.execute(
        text(
            """
            SELECT s.symbol, sc.score, sc.setup_status, f.volume_ratio, f.rs_score, sc.regime as stock_phase, sc.stop_loss, sc.tp_zone
            FROM stock_scores sc
            JOIN stocks s ON s.id = sc.stock_id
            JOIN stock_features f ON f.stock_id = s.id AND f.date = sc.date
            WHERE sc.date = :target_date
              AND sc.trade_signal IN ('BUY', 'SETUP') 
              AND sc.setup_status NOT IN ('LOW_LIQUIDITY', 'INVALID_PHASE')
            ORDER BY sc.score DESC
            LIMIT 5
            """
        ),
        {"target_date": target_date}
    ).fetchall()

    stock_list = []
    for row in top_stocks:
        stock_list.append({
            "Mã": row.symbol,
            "Điểm": round(row.score, 1),
            "Pha": row.stock_phase,
            "Trạng thái": row.setup_status,
            "Đột biến KL (Volume Ratio)": round(row.volume_ratio, 1) if row.volume_ratio else None,
            "Sức mạnh tương đối (RS)": round(row.rs_score, 1) if row.rs_score else None,
            "Giá Cắt Lỗ": round(row.stop_loss, 2) if row.stop_loss else None,
            "Giá Chốt Lời Mục Tiêu": round(row.tp_zone, 2) if row.tp_zone else None,
        })
        
    # 3. Lấy Top 3 ngành mạnh nhất (Tính dựa trên trung bình điểm các cổ phiếu)
    sector_data = session.execute(
        text(
            """
            SELECT s.sector, AVG(sc.score) as avg_score, COUNT(s.id) as stock_count
            FROM stock_scores sc
            JOIN stocks s ON s.id = sc.stock_id
            WHERE sc.date = :target_date AND s.sector != ''
            GROUP BY s.sector
            ORDER BY avg_score DESC
            LIMIT 3
            """
        ),
        {"target_date": target_date}
    ).fetchall()
    
    sector_list = [{"Ngành": row.sector, "Điểm trung bình": round(row.avg_score, 1), "Số CP": row.stock_count} for row in sector_data]

    # 4. Lấy thông tin về Danh mục đầu tư cá nhân (User Portfolio)
    user_portfolio = []
    
    # Query all symbols from portfolio table
    portfolio_rows = session.query(models.Portfolio).all()
    portfolio_symbols = [row.symbol for row in portfolio_rows] if portfolio_rows else []
    
    if portfolio_symbols:
        placeholders = ', '.join(f"'{sym}'" for sym in portfolio_symbols)
        port_stocks = session.execute(
            text(
                f"""
                SELECT s.symbol, 
                       COALESCE(sc.score, 0) as score, 
                       COALESCE(sc.setup_status, 'NO DATA') as setup_status, 
                       COALESCE(f.volume_ratio, 1.0) as volume_ratio, 
                       COALESCE(f.rs_score, 0) as rs_score, 
                       COALESCE(sc.regime, 'UNKNOWN') as stock_phase,
                       sc.stop_loss,
                       sc.tp_zone
                FROM stocks s
                LEFT JOIN stock_scores sc ON s.id = sc.stock_id AND sc.date = :target_date
                LEFT JOIN stock_features f ON s.id = f.stock_id AND f.date = :target_date
                WHERE s.symbol IN ({placeholders})
                """
            ),
            {"target_date": target_date}
        ).fetchall()
        
        for row in port_stocks:
            user_portfolio.append({
                "Mã": row.symbol,
                "Điểm": round(row.score, 1) if row.score else 0,
                "Pha": row.stock_phase,
                "Tín hiệu hiện tại": row.setup_status,
                "Sức mạnh tương đối (RS)": round(row.rs_score, 1) if row.rs_score else 0,
                "Giá Cắt Lỗ": round(row.stop_loss, 2) if row.stop_loss else None,
                "Giá Chốt Lời Mục Tiêu": round(row.tp_zone, 2) if row.tp_zone else None,
            })

    # 5. Thu thập tin tức mới nhất từ RSS Feed (VnExpress Kinh Doanh / CafeF) để đánh giá Sentiment
    news_titles = []
    try:
        # Lấy tin từ VNExpress Kinh doanh (nhanh và ít chặn)
        feed_url = 'https://vnexpress.net/rss/kinh-doanh.rss'
        feed = feedparser.parse(feed_url)
        # Chỉ lấy 10 tin mới nhất để nén vào prompt
        for entry in feed.entries[:10]:
            news_titles.append(entry.title)
    except Exception as e:
        logger.error(f"Failed to fetch RSS news: {e}")

    payload = {
        "Vĩ mô / Thị trường": market_data,
        "Top Nhóm ngành Dẫn dắt": sector_list,
        "Top Cổ phiếu Nổi bật (Hệ thống quét)": stock_list,
        "Danh mục Đầu tư Đang nắm giữ": user_portfolio,
        "Tin tức Kinh tế / Tài chính mới nhất (Sentiment Context)": news_titles
    }
    
    return payload
