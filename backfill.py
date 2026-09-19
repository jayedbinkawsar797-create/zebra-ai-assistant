import os
import asyncio
import httpx
import database
from dotenv import load_dotenv

load_dotenv()

QUO_API_KEY = os.getenv("QUO_API_KEY")

STOP_DATE_STR = "2026-03-01T00:00:00Z"

async def fetch_and_store_history():
    print("🔄 Starting massive Quo History Backfill (Since March)...")
    database.init_db()
    
    url = "https://api.openphone.com/v1/messages"
    headers = {
        "Authorization": f"{QUO_API_KEY}",
        "Content-Type": "application/json"
    }
    
    all_messages_to_insert = []
    page_token = None
    
    async with httpx.AsyncClient() as client:
        query = "?maxResults=100"
        print(f"📡 Fetching a batch of 100 messages from Quo...")
        response = await client.get(f"{url}{query}", headers=headers, timeout=30.0)
        
        if response.status_code != 200:
            print(f"❌ Error fetching from Quo API! Status: {response.status_code}")
            print(f"❌ Exact Quo Error Message: {response.text}")
            return
            
        data = response.json()
        print("✅ Success! You have connected.")

if __name__ == "__main__":
    asyncio.run(fetch_and_store_history())
