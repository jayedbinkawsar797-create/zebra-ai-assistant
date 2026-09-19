import os
import asyncio
import httpx
import database
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

QUO_API_KEY = os.getenv("QUO_API_KEY")
QUO_FROM_NUMBER = os.getenv("QUO_FROM_NUMBER", "+19548204220")

# Stop backfilling when we hit messages older than this date
STOP_DATE_STR = "2026-03-01T00:00:00Z"

async def fetch_and_store_history():
    print("🔄 Starting massive Quo History Backfill (Since March)...")
    database.init_db()
    
    url = "https://api.openphone.com/v1/messages"
    headers = {
        "Authorization": f"Bearer {QUO_API_KEY}",
        "Content-Type": "application/json"
    }
    
    all_messages_to_insert = []
    page_token = None
    total_fetched = 0
    reached_march = False
    
    async with httpx.AsyncClient() as client:
        while not reached_march:
            query = "?limit=100"
            if page_token:
                query += f"&pageToken={page_token}"
                
            print(f"📡 Fetching a batch of 100 messages from Quo...")
            try:
                response = await client.get(f"{url}{query}", headers=headers, timeout=30.0)
                response.raise_for_status()
                data = response.json()
            except Exception as e:
                print(f"❌ Error fetching from Quo API: {e}")
                break
                
            messages = data.get("data", [])
            if not messages:
                break
                
            for msg in messages:
                created_at = msg.get("createdAt")
                # If we've hit a message older than March, stop paginating
                if created_at and created_at < STOP_DATE_STR:
                    reached_march = True
                    break
                    
                all_messages_to_insert.append(msg)
                
            total_fetched += len(messages)
            page_token = data.get("nextPageToken")
            
            # If no more pages or we hit March, we are done downloading
            if not page_token:
                break
                
        print(f"📦 Total messages downloaded since March: {len(all_messages_to_insert)}")
        
        # Quo returns newest first. We reverse it so oldest goes into the DB first.
        all_messages_to_insert.reverse()
        
        inserted = 0
        for msg in all_messages_to_insert:
            direction = msg.get("direction")
            content = msg.get("content", "")
            
            if not content:
                continue
                
            if direction == "incoming":
                role = "user"
                phone = msg.get("from")
            else:
                role = "assistant"
                to_list = msg.get("to", [])
                if not to_list:
                    continue
                phone = to_list[0]
                
            if phone:
                database.save_message(phone, role, content)
                inserted += 1
                
        print(f"✅ Successfully organized and inserted {inserted} historical messages into the AI's Brain!")

if __name__ == "__main__":
    asyncio.run(fetch_and_store_history())
