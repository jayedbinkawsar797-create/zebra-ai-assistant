import os
import httpx

QUO_API_KEY = os.getenv("QUO_API_KEY")
QUO_FROM_NUMBER = os.getenv("QUO_FROM_NUMBER", "+19548204220")

async def send_sms(to_number: str, text: str, media_url: str = None):
    url = "https://api.openphone.com/v1/messages"
    headers = {
        "Authorization": f"Bearer {QUO_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "from": QUO_FROM_NUMBER,
        "to": [to_number],
        "content": text
    }
    
    if media_url:
        # Assuming Quo handles direct image links
        payload["media"] = [{"url": media_url, "type": "image/jpeg"}]
        
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, headers=headers, json=payload, timeout=10.0)
            response.raise_for_status()
            print(f"✅ Quo SMS sent to {to_number}")
            return response.json()
        except Exception as e:
            print(f"❌ Quo SMS failed: {e}")
            return None
