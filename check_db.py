import database

conn = database.get_connection()
if not conn:
    print("❌ ERROR: Could not connect to database. DATABASE_URL is missing or invalid.")
else:
    print("✅ Connected to Database!")
    with conn.cursor() as cur:
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public';
        """)
        tables = cur.fetchall()
        if not tables:
            print("⚠️ No tables found in the database.")
        else:
            print("📦 Found the following tables:")
            for t in tables:
                print(f" - {t['table_name']}")
                
        # Let's forcefully run init_db just to be sure
        print("\nForcefully running init_db()...")
        database.init_db()
        
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public';
        """)
        tables2 = cur.fetchall()
        print("\n📦 Tables after forceful init:")
        for t in tables2:
            print(f" - {t['table_name']}")
