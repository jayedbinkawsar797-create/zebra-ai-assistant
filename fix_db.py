import database

def fix_database_columns():
    conn = database.get_connection()
    if not conn:
        print("❌ ERROR: Could not connect to database.")
        return
        
    try:
        with conn.cursor() as cur:
            print("⏳ Adding missing columns to zebra_leads...")
            cur.execute("""
                ALTER TABLE zebra_leads
                ADD COLUMN IF NOT EXISTS last_name VARCHAR(100),
                ADD COLUMN IF NOT EXISTS email VARCHAR(255),
                ADD COLUMN IF NOT EXISTS zip_code VARCHAR(20),
                ADD COLUMN IF NOT EXISTS buying_timeline VARCHAR(100),
                ADD COLUMN IF NOT EXISTS budget_preference VARCHAR(100),
                ADD COLUMN IF NOT EXISTS utm_source VARCHAR(255),
                ADD COLUMN IF NOT EXISTS utm_campaign VARCHAR(255),
                ADD COLUMN IF NOT EXISTS fbclid VARCHAR(255),
                ADD COLUMN IF NOT EXISTS landing_page_url TEXT;
            """)
            conn.commit()
            print("✅ SUCCESS: All missing columns have been added!")
    except Exception as e:
        print(f"❌ Error updating database: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    fix_database_columns()
