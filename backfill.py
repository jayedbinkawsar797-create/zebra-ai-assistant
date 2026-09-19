import os
import asyncio
import httpx
import database
from dotenv import load_dotenv

load_dotenv()

QUO_API_KEY = os.getenv("QUO_API_KEY")
QUO_FROM_NUMBER = os.getenv("QUO_FROM_NUMBER", "+19548204220")

async def fetch_and_store_history():
    print("🔄 Starting Quo History Backfill...")
    database.init_db()
    
    url = "https://api.openphone.com/v1/messages"
    headers = {
        "Authorization": f"Bearer {QUO_API_KEY}",
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            # We fetch the last 100 messages as a starting point.
            # In a full production script, you'd handle pagination (nextPageToken).
            response = await client.get(f"{url}?limit=100", headers=headers, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            
            messages = data.get("data", [])
            print(f"📦 Fetched {len(messages)} recent messages from Quo.")
            
            # Quo returns messages newest first, so we reverse to insert oldest first
            messages.reverse()
            
            inserted = 0
            for msg in messages:
                direction = msg.get("direction")
                content = msg.get("content", "")
                
                if not content:
                    continue
                    
                if direction == "incoming":
                    role = "user"
                    phone = msg.get("from")
                else:
                    role = "assistant"
                    # For outgoing, 'to' is a list
                    to_list = msg.get("to", [])
                    if not to_list:
                        continue
                    phone = to_list[0]
                    
                if phone:
                    database.save_message(phone, role, content)
                    inserted += 1
                    
            print(f"✅ Successfully backfilled {inserted} messages into PostgreSQL!")
            
        except Exception as e:
            print(f"❌ Error during backfill: {e}")

if __name__ == "__main__":
    asyncio.run(fetch_and_store_history())
