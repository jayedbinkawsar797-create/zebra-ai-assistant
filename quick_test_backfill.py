import os
import asyncio
import httpx
import database
from dotenv import load_dotenv

load_dotenv()

QUO_API_KEY = os.getenv("QUO_API_KEY")
QUO_FROM_NUMBER = os.getenv("QUO_FROM_NUMBER", "+19548204220")

# The exact ID of the Primary Inbox
PRIMARY_INBOX_ID = "PNlX7nJ6iG"

async def get_all_conversations(client, headers):
    customer_numbers = set()
    page_token = None
    print(f"👥 Scanning ONLY the Primary Inbox ({PRIMARY_INBOX_ID})...")
    
    while True:
        # Filter conversations by the exact Inbox ID!
        url = f"https://api.openphone.com/v1/conversations?maxResults=100&phoneNumberId={PRIMARY_INBOX_ID}"
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

async def fetch_messages_for_contact(client, headers, contact_number):
    url = "https://api.openphone.com/v1/messages"
    params = {
        "phoneNumberId": PRIMARY_INBOX_ID,
        "maxResults": 100,
        "participants": [contact_number]
    }
    
    resp = await client.get(url, headers=headers, params=params)
    if resp.status_code == 200:
        return resp.json().get("data", [])
    return []

async def run_quick_test():
    database.init_db()
    headers = {
        "Authorization": f"{QUO_API_KEY}",
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        contacts = await get_all_conversations(client, headers)
        
        # WE WILL ONLY DO THE FIRST 5 FOR A LIGHTNING FAST TEST
        print(f"✅ Found {len(contacts)} unique customers in the Primary Inbox.")
        print("⚡ RUNNING LIGHTNING FAST TEST ON 5 CUSTOMERS...")
        
        test_contacts = contacts[:5]
        total_inserted = 0
        
        for i, contact_number in enumerate(test_contacts):
            print(f"📥 Fetching history for {i+1}/5: {contact_number}...")
            messages = await fetch_messages_for_contact(client, headers, contact_number)
            
            if not messages:
                continue
                
            messages.reverse()
            for msg in messages:
                content = msg.get("content", "")
                if not content: continue
                direction = msg.get("direction")
                role = "user" if direction == "incoming" else "assistant"
                
                # Save to database
                database.save_message(contact_number, role, content)
                total_inserted += 1
                
        print(f"🎉 SUCCESS! Injected {total_inserted} messages directly into Postgres.")

if __name__ == "__main__":
    asyncio.run(run_quick_test())
