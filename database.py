import os
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.getenv("DATABASE_URL")

def get_connection():
    if not DATABASE_URL:
        return None
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def init_db():
    conn = get_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS zebra_messages (
                    id SERIAL PRIMARY KEY,
                    phone_number VARCHAR(50),
                    role VARCHAR(50),
                    content TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS zebra_leads (
                    id SERIAL PRIMARY KEY,
                    phone_number VARCHAR(50) UNIQUE,
                    first_name VARCHAR(100),
                    ai_paused BOOLEAN DEFAULT FALSE,
                    followup_count INTEGER DEFAULT 0,
                    model_interest VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()
    finally:
        conn.close()

def get_chat_history(phone_number, limit=20):
    conn = get_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT role, content FROM zebra_messages 
                WHERE phone_number = %s 
                ORDER BY created_at ASC LIMIT %s
            """, (phone_number, limit))
            return cur.fetchall()
    finally:
        conn.close()

def save_message(phone_number, role, content):
    conn = get_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO zebra_messages (phone_number, role, content) 
                VALUES (%s, %s, %s)
            """, (phone_number, role, content))
            
            cur.execute("""
                INSERT INTO zebra_leads (phone_number) 
                VALUES (%s) 
                ON CONFLICT (phone_number) DO NOTHING;
            """, (phone_number,))
            conn.commit()
    finally:
        conn.close()

def get_lead(phone_number):
    conn = get_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM zebra_leads WHERE phone_number = %s", (phone_number,))
            return cur.fetchone()
    finally:
        conn.close()

def pause_ai_for_lead(phone_number):
    conn = get_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE zebra_leads SET ai_paused = TRUE WHERE phone_number = %s;", (phone_number,))
            conn.commit()
    finally:
        conn.close()

def get_leads_needing_followup():
    conn = get_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT m.phone_number 
                FROM zebra_messages m
                JOIN zebra_leads l ON l.phone_number = m.phone_number
                WHERE l.ai_paused = FALSE AND l.followup_count < 2
                GROUP BY m.phone_number, l.followup_count
                HAVING MAX(m.created_at) < NOW() - INTERVAL '24 hours'
            """)
            return cur.fetchall()
    finally:
        conn.close()

def increment_followup(phone_number):
    conn = get_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE zebra_leads SET followup_count = followup_count + 1 WHERE phone_number = %s", (phone_number,))
            conn.commit()
    finally:
        conn.close()
