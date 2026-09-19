import os
import asyncio
import httpx
import json
import database
from dotenv import load_dotenv

load_dotenv()

QUO_API_KEY = os.getenv("QUO_API_KEY")
QUO_FROM_NUMBER = os.getenv("QUO_FROM_NUMBER", "+19548204220")

async def get_phone_number_id(client, headers):
    print("🔍 Finding your Quo Inbox ID...")
    resp = await client.get("https://api.openphone.com/v1/phone-numbers", headers=headers)
    if resp.status_code != 200:
        print(f"Failed to get phone numbers: {resp.text}")
        return None
    data = resp.json().get("data", [])
    for number in data:
        if number.get("number") == QUO_FROM_NUMBER:
            return number.get("id")
    if data:
        return data[0].get("id")
    return None

async def get_all_conversations(client, headers):
    print("👥 Scanning all your past conversations...")
    customer_numbers = set()
    page_token = None
    
    while True:
        url = "https://api.openphone.com/v1/conversations?maxResults=100"
        if page_token:
            url += f"&pageToken={page_token}"
            
        resp = await client.get(url, headers=headers)
        if resp.status_code != 200:
            print(f"Failed to get conversations: {resp.text}")
            break
            
        data = resp.json()
        conversations = data.get("data", [])
        
        for conv in conversations:
            participants = conv.get("participants", [])
            for p in participants:
                # Add any participant that isn't your own number
                if p != QUO_FROM_NUMBER and p.startswith("+"):
                    customer_numbers.add(p)
                    
        page_token = data.get("nextPageToken")
        if not page_token:
            break
            
    return list(customer_numbers)

async def fetch_messages_for_contact(client, headers, phone_id, contact_number):
    url = "https://api.openphone.com/v1/messages"
    participants_str = json.dumps([contact_number])
    query = f"?maxResults=100&phoneNumberId={phone_id}&participants={participants_str}"
    
    resp = await client.get(url + query, headers=headers)
    if resp.status_code == 200:
        return resp.json().get("data", [])
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
            print("❌ Could not find the Inbox ID.")
            return
        print(f"✅ Found Inbox ID: {phone_id}")
        
        contacts = await get_all_conversations(client, headers)
        print(f"✅ Found {len(contacts)} unique customer phone numbers.")
        
        total_inserted = 0
        for i, contact_number in enumerate(contacts):
            print(f"📥 Fetching history for customer {i+1}/{len(contacts)}: {contact_number}")
            messages = await fetch_messages_for_contact(client, headers, phone_id, contact_number)
            
            if not messages:
                continue
                
            messages.reverse()
            
            for msg in messages:
                content = msg.get("content", "")
                if not content:
                    continue
                direction = msg.get("direction")
                role = "user" if direction == "incoming" else "assistant"
                database.save_message(contact_number, role, content)
                total_inserted += 1
                
            await asyncio.sleep(0.5)
            
        print(f"🎉 SUCCESS! Completely rebuilt database with {total_inserted} historical messages.")

if __name__ == "__main__":
    asyncio.run(run_advanced_backfill())
