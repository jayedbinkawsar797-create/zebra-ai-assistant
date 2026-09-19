import os
import asyncio
import httpx
import database
from dotenv import load_dotenv

load_dotenv()

QUO_API_KEY = os.getenv("QUO_API_KEY")
QUO_FROM_NUMBER = os.getenv("QUO_FROM_NUMBER", "+19548204220")

# Stop date for full script
STOP_DATE_STR = "2026-03-01T00:00:00Z"

async def get_phone_number_id(client, headers):
    resp = await client.get("https://api.openphone.com/v1/phone-numbers", headers=headers)
    if resp.status_code != 200:
        return None
    data = resp.json().get("data", [])
    
    for number in data:
        print(f"Checking inbox: {number.get('name')} -> {number.get('number')} (ID: {number.get('id')})")
        if number.get("number") == QUO_FROM_NUMBER:
            return number.get("id")
            
    if data:
        print(f"WARNING: Did not find exact match for {QUO_FROM_NUMBER}. Using first inbox.")
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
    
    # Httpx handles array serialization cleanly when passed as a list
    params = {
        "phoneNumberId": phone_id,
        "maxResults": 100,
        "participants": [contact_number]
    }
    
    all_msgs = []
    page_token = None
    
    while True:
        if page_token:
            params["pageToken"] = page_token
            
        resp = await client.get(url, headers=headers, params=params)
        if resp.status_code == 200:
            data = resp.json()
            messages = data.get("data", [])
            if not messages:
                break
                
            for msg in messages:
                created_at = msg.get("createdAt")
                if created_at and created_at < STOP_DATE_STR:
                    return all_msgs + messages
                    
            all_msgs.extend(messages)
            page_token = data.get("nextPageToken")
            if not page_token:
                break
        else:
            print(f"❌ API Error for {contact_number}: {resp.status_code} - {resp.text}")
            break
            
    return all_msgs

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
        print(f"✅ Found {len(contacts)} unique customers. Running backfill since March...")
        
        total_inserted = 0
        
        for i, contact_number in enumerate(contacts):
            print(f"📥 Fetching history for {i+1}/{len(contacts)}: {contact_number}...")
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
