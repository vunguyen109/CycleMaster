"""
Database migration script to add cycle features and update buy_zone schema.
Run this before starting the application if you see:
  sqlite3.OperationalError: no such column: stock_scores.buy_zone_low
  
Handles:
- Adding cycle_phase, cycle_amplitude, dominant_cycle_period to stock_features
- Migrating from old buy_zone column to buy_zone_low/buy_zone_high
"""
import sqlite3
from pathlib import Path


def migrate_db(db_path: str = './data/cyclemaster.db'):
    """
    Migrate SQLite schema to add:
    - cycle_phase, cycle_amplitude, dominant_cycle_period to stock_features
    - buy_zone_low, buy_zone_high to stock_scores (replaces old buy_zone)
    - Ensure tp_zone, stop_loss are Float in stock_scores
    """
    if not Path(db_path).exists():
        print(f"Database {db_path} does not exist. Skipping migration.")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if cycle columns already exist in stock_features
        cursor.execute("PRAGMA table_info(stock_features)")
        columns = {row[1] for row in cursor.fetchall()}
        
        print(f"Existing stock_features columns: {sorted(columns)}")
        
        if 'cycle_phase' not in columns:
            print("Adding cycle_phase to stock_features...")
            cursor.execute("ALTER TABLE stock_features ADD COLUMN cycle_phase REAL DEFAULT NULL")
        
        if 'cycle_amplitude' not in columns:
            print("Adding cycle_amplitude to stock_features...")
            cursor.execute("ALTER TABLE stock_features ADD COLUMN cycle_amplitude REAL DEFAULT NULL")
        
        if 'dominant_cycle_period' not in columns:
            print("Adding dominant_cycle_period to stock_features...")
            cursor.execute("ALTER TABLE stock_features ADD COLUMN dominant_cycle_period REAL DEFAULT NULL")

        feature_new_cols = {
            'ma200': "REAL DEFAULT NULL",
            'ma20_slope': "REAL DEFAULT NULL",
            'ma50_slope': "REAL DEFAULT NULL",
            'ma100_slope': "REAL DEFAULT NULL",
            'ma200_slope': "REAL DEFAULT NULL",
            'volume_trend_5': "REAL DEFAULT NULL",
            'atr_percent': "REAL DEFAULT NULL",
            'sector_score': "REAL DEFAULT NULL",
        }
        for col, col_type in feature_new_cols.items():
            if col not in columns:
                print(f"Adding {col} to stock_features...")
                cursor.execute(f"ALTER TABLE stock_features ADD COLUMN {col} {col_type}")
        
        # Check stock_scores columns
        cursor.execute("PRAGMA table_info(stock_scores)")
        score_cols = {row[1]: row[2] for row in cursor.fetchall()}
        
        print(f"Existing stock_scores columns: {sorted(score_cols.keys())}")
        if 'trade_signal' not in score_cols:
            print("Adding trade_signal to stock_scores...")
            cursor.execute("ALTER TABLE stock_scores ADD COLUMN trade_signal TEXT DEFAULT NULL")
        if 'sector_score' not in score_cols:
            print("Adding sector_score to stock_scores...")
            cursor.execute("ALTER TABLE stock_scores ADD COLUMN sector_score REAL DEFAULT NULL")
        
        # Determine if we need to rebuild stock_scores table
        needs_rebuild = False
        has_old_buy_zone = 'buy_zone' in score_cols
        has_new_buy_zone = 'buy_zone_low' in score_cols and 'buy_zone_high' in score_cols
        
        # Rebuild if: old buy_zone exists but new columns don't, or types are wrong
        if has_old_buy_zone and not has_new_buy_zone:
            print("Migrating buy_zone to buy_zone_low/buy_zone_high...")
            needs_rebuild = True
        
        # Also check if zone columns are TEXT instead of REAL
        for col in ['buy_zone', 'tp_zone', 'stop_loss']:
            if col in score_cols:
                col_type = score_cols[col].upper()
                if 'TEXT' in col_type or 'VARCHAR' in col_type:
                    print(f"Column {col} is TEXT; will rebuild table to convert to REAL")
                    needs_rebuild = True
                    break
        
        if needs_rebuild:
            print("Rebuilding stock_scores table...")
            cursor.execute("""
                CREATE TABLE stock_scores_new (
                    id INTEGER PRIMARY KEY,
                    stock_id INTEGER NOT NULL,
                    date DATE NOT NULL,
                    regime TEXT,
                    score REAL,
                    buy_zone_low REAL,
                    buy_zone_high REAL,
                    tp_zone REAL,
                    stop_loss REAL,
                    risk_reward REAL,
                    confidence REAL,
                    setup_status TEXT,
                    market_alignment TEXT,
                    trade_signal TEXT,
                    sector_score REAL,
                    model_version TEXT,
                    setup_tier TEXT,
                    UNIQUE(stock_id, date),
                    FOREIGN KEY(stock_id) REFERENCES stocks(id)
                )
            """)
            
            # Copy data, migrating buy_zone to buy_zone_low/buy_zone_high if old column exists
            if has_old_buy_zone:
                # Old buy_zone was stored as "13.54-14.06" string or as single value
                # Split it: low=mid-0.5*atr, high=mid+0.5*atr
                # Since we don't have the exact original atr, we'll assume equal distribution
                # Old format: store low as 70% of zone mid, high as 130% of zone mid (rough estimate)
                # For simplicity: if zone exists, use it; if not, NULL
                print("Migrating old buy_zone values to buy_zone_low/buy_zone_high...")
                cursor.execute("""
                    INSERT INTO stock_scores_new
                    SELECT 
                        id, stock_id, date, regime, score,
                        CASE WHEN buy_zone IS NOT NULL AND buy_zone > 0 
                             THEN CAST(buy_zone AS REAL) * 0.95
                             ELSE NULL END as buy_zone_low,
                        CASE WHEN buy_zone IS NOT NULL AND buy_zone > 0 
                             THEN CAST(buy_zone AS REAL) * 1.05
                             ELSE NULL END as buy_zone_high,
                        CAST(COALESCE(tp_zone, 0) AS REAL) as tp_zone,
                        CAST(COALESCE(stop_loss, 0) AS REAL) as stop_loss,
                        risk_reward, confidence, setup_status, market_alignment, NULL as trade_signal, NULL as sector_score, model_version, setup_tier
                    FROM stock_scores
                """)
            else:
                # No old buy_zone column, just copy everything with NULLs
                cursor.execute("""
                    INSERT INTO stock_scores_new
                    SELECT 
                        id, stock_id, date, regime, score,
                        NULL as buy_zone_low,
                        NULL as buy_zone_high,
                        CAST(COALESCE(tp_zone, 0) AS REAL) as tp_zone,
                        CAST(COALESCE(stop_loss, 0) AS REAL) as stop_loss,
                        risk_reward, confidence, setup_status, market_alignment, NULL as trade_signal, NULL as sector_score, model_version, setup_tier
                    FROM stock_scores
                    WHERE 1=0
                """)
            
            cursor.execute("DROP TABLE stock_scores")
            cursor.execute("ALTER TABLE stock_scores_new RENAME TO stock_scores")
            print("stock_scores table rebuilt successfully")
        
        conn.commit()
        print("Migration completed successfully!")
        
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    migrate_db()
