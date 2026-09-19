import os
import asyncio
import httpx
import database
from dotenv import load_dotenv

load_dotenv()

QUO_API_KEY = os.getenv("QUO_API_KEY")
QUO_FROM_NUMBER = os.getenv("QUO_FROM_NUMBER", "+19548204220")

async def get_phone_number_id(client, headers):
    resp = await client.get("https://api.openphone.com/v1/phone-numbers", headers=headers)
    if resp.status_code != 200:
        return None
    data = resp.json().get("data", [])
    for number in data:
        if number.get("number") == QUO_FROM_NUMBER:
            return number.get("id")
    if data:
        return data[0].get("id")
    return None

async def get_all_conversations(client, headers):
    customer_numbers = set()
    page_token = None
    while True:
        url = "https://api.openphone.com/v1/conversations?maxResults=100"
        if page_token:
            url += f"&pageToken={page_token}"
        resp = await client.get(url, headers=headers)
        if resp.status_code != 200:
            break
        data = resp.json()
        for conv in data.get("data", []):
            for p in conv.get("participants", []):
                if p != QUO_FROM_NUMBER and p.startswith("+"):
                    customer_numbers.add(p)
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return list(customer_numbers)

async def fetch_messages_for_contact(client, headers, phone_id, contact_number):
    url = "https://api.openphone.com/v1/messages"
    
    # Try multiple ways of sending the array just in case
    # Format 1: ?participants=["+1..."] (URL encoded)
    params = {
        "phoneNumberId": phone_id,
        "maxResults": 100,
        "participants": f'["{contact_number}"]'
    }
    
    resp = await client.get(url, headers=headers, params=params)
    if resp.status_code == 200:
        return resp.json().get("data", [])
        
    # Format 2: ?participants=+1...
    params2 = {
        "phoneNumberId": phone_id,
        "maxResults": 100,
        "participants": contact_number
    }
    resp2 = await client.get(url, headers=headers, params=params2)
    if resp2.status_code == 200:
        return resp2.json().get("data", [])
        
    print(f"❌ Failed to fetch messages. Error: {resp.text}")
    return []

async def run_advanced_backfill():
    database.init_db()
    headers = {
        "Authorization": f"{QUO_API_KEY}",
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        phone_id = await get_phone_number_id(client, headers)
        if not phone_id:
            return
            
        contacts = await get_all_conversations(client, headers)
        
        # WE WILL ONLY DO THE FIRST 5 FOR NOW TO TEST
        print(f"✅ Found {len(contacts)} unique customers. Testing the first 5...")
        test_contacts = contacts[:5]
        
        total_inserted = 0
        for i, contact_number in enumerate(test_contacts):
            print(f"📥 Fetching history for {contact_number}...")
            messages = await fetch_messages_for_contact(client, headers, phone_id, contact_number)
            
            if not messages:
                continue
                
            messages.reverse()
            for msg in messages:
                content = msg.get("content", "")
                if not content: continue
                direction = msg.get("direction")
                role = "user" if direction == "incoming" else "assistant"
                database.save_message(contact_number, role, content)
                total_inserted += 1
                
        print(f"🎉 SUCCESS! Rebuilt database with {total_inserted} historical messages.")

if __name__ == "__main__":
    asyncio.run(run_advanced_backfill())
