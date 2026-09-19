import psycopg2
import os

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("ALTER TABLE zebra_leads ADD COLUMN IF NOT EXISTS followup_count INTEGER DEFAULT 0;")
        conn.commit()
        conn.close()
    except Exception as e:
        pass
