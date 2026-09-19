import os
import json
from openai import AsyncOpenAI
import database

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

with open("knowledge.json", "r") as f:
    ZEBRA_KNOWLEDGE = f.read()

SYSTEM_PROMPT = f"""
You are Alex, a friendly, professional luxury sales specialist for Zebra Golf Cart.
Keep SMS messages very short (1-3 sentences max). Sound like a real human.
Do not sound like a bot. 
Only answer based on the knowledge provided. Do not hallucinate prices.
If the customer asks for a picture, pretend you attached it in the text.
If the customer says words like STOP, UNSUBSCRIBE, CANCEL, output exactly: [STOP]
If the customer explicitly asks for a human, asks for a custom trade-in appraisal, or wants to schedule a phone call / asks someone to call them, output exactly: [HUMAN_TAKEOVER]

Knowledge Base:
{ZEBRA_KNOWLEDGE}
"""

async def generate_reply(phone_number: str, new_message: str):
    # 1. Check stop words locally
    if new_message.strip().upper() in ["STOP", "UNSUBSCRIBE", "CANCEL"]:
        return "[STOP]"
    
    # 2. Fetch history
    history_records = database.get_chat_history(phone_number, limit=15)
    
    # 3. Format messages for OpenAI
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in history_records:
        messages.append({"role": msg["role"], "content": msg["content"]})
    
    # Add the current message
    messages.append({"role": "user", "content": new_message})
    
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.7,
            max_tokens=150
        )
        reply = response.choices[0].message.content
        return reply
    except Exception as e:
        print(f"❌ OpenAI Error: {e}")
        return "I'm having a little trouble connecting right now, let me have one of our team members reach out to you shortly!"
