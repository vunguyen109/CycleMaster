"""
Database migration script to add cycle features and fix zone column types.
Run this before starting the application if you see:
  sqlite3.OperationalError: no such column: stock_features.cycle_phase
"""
import sqlite3
from pathlib import Path


def migrate_db(db_path: str = './data/cyclemaster.db'):
    """
    Migrate SQLite schema to add:
    - cycle_phase, cycle_amplitude, dominant_cycle_period to stock_features
    - Ensure buy_zone, tp_zone, stop_loss are Float in stock_scores
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
        
        # Check stock_scores columns
        cursor.execute("PRAGMA table_info(stock_scores)")
        score_cols = {row[1]: row[2] for row in cursor.fetchall()}
        
        print(f"Existing stock_scores columns: {sorted(score_cols.keys())}")
        
        # Check if zone columns are TEXT instead of REAL; if so, they need a schema rebuild
        # SQLite doesn't support ALTER COLUMN, so we recreate the table if needed
        needs_rebuild = False
        for col in ['buy_zone', 'tp_zone', 'stop_loss']:
            if col in score_cols:
                col_type = score_cols[col].upper()
                if 'TEXT' in col_type or 'VARCHAR' in col_type:
                    print(f"Column {col} is TEXT; will rebuild table to convert to REAL")
                    needs_rebuild = True
                    break
        
        if needs_rebuild:
            print("Rebuilding stock_scores table to fix column types...")
            cursor.execute("""
                CREATE TABLE stock_scores_new (
                    id INTEGER PRIMARY KEY,
                    stock_id INTEGER NOT NULL,
                    date DATE NOT NULL,
                    regime TEXT,
                    score REAL,
                    buy_zone REAL,
                    tp_zone REAL,
                    stop_loss REAL,
                    risk_reward REAL,
                    confidence REAL,
                    setup_status TEXT,
                    market_alignment TEXT,
                    model_version TEXT,
                    setup_tier TEXT,
                    UNIQUE(stock_id, date),
                    FOREIGN KEY(stock_id) REFERENCES stocks(id)
                )
            """)
            
            # Copy data, converting zone columns to REAL
            cursor.execute("""
                INSERT INTO stock_scores_new
                SELECT 
                    id, stock_id, date, regime, score,
                    CAST(buy_zone AS REAL) as buy_zone,
                    CAST(tp_zone AS REAL) as tp_zone,
                    CAST(stop_loss AS REAL) as stop_loss,
                    risk_reward, confidence, setup_status, market_alignment, model_version, setup_tier
                FROM stock_scores
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
