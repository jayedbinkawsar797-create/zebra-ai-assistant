import os
import re
import uvicorn
import asyncio
from fastapi import FastAPI, Request, BackgroundTasks
from pydantic import BaseModel
from dotenv import load_dotenv

import database
import quo
import agent
import scheduler

load_dotenv()

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    database.init_db()
    asyncio.create_task(scheduler.start_scheduler())

async def process_incoming_message(from_number: str, text: str):
    ai_reply = await agent.generate_reply(from_number, text)
    
    if "[STOP]" in ai_reply:
        database.pause_ai_for_lead(from_number)
        return
        
    if "[HUMAN_TAKEOVER]" in ai_reply:
        database.pause_ai_for_lead(from_number)
        handoff_msg = "I'd be happy to schedule a call with one of our specialists. I'll have them reach out to you shortly!"
        database.save_message(from_number, "assistant", handoff_msg)
        await quo.send_sms(from_number, handoff_msg)
        return

    media_url = None
    image_match = re.search(r"\[IMAGE:\s*(https?://[^\s\]]+)\]", ai_reply)
    if image_match:
        media_url = image_match.group(1)
        ai_reply = ai_reply.replace(image_match.group(0), "").strip()
        
    typing_delay = min(12, max(4, len(ai_reply) / 20))
    await asyncio.sleep(typing_delay)
    
    database.save_message(from_number, "assistant", ai_reply)
    await quo.send_sms(from_number, ai_reply, media_url=media_url)

@app.post("/webhooks/quo")
async def handle_quo_webhook(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    
    if payload.get("type") == "message.received":
        data = payload.get("data", {})
        direction = data.get("direction")
        phone_number = data.get("to", [""])[0] if direction == "outgoing" else data.get("from")
        text = data.get("content", "")
        
        # ULTRA AUDIT FIX: Detect human takeover safely!
        # If an outgoing message is sent, we check if the AI sent it by looking in our DB.
        # If the text isn't in our DB, it means YOU typed it from the Quo app, so we PAUSE the AI!
        if direction == "outgoing":
            history = database.get_chat_history(phone_number, limit=5)
            # Check if this exact message was recently logged as an assistant message
            was_sent_by_ai = any(msg["role"] == "assistant" and msg["content"].strip() == text.strip() for msg in history)
            
            if not was_sent_by_ai:
                database.pause_ai_for_lead(phone_number)
                print(f"🛑 You manually texted {phone_number}. AI is now permanently paused for them.")
            return {"status": "ignored_outgoing"}
            
        # Incoming messages
        lead = database.get_lead(phone_number)
        if lead and lead.get("ai_paused"):
            return {"status": "ai_paused"}
            
        database.save_message(phone_number, "user", text)
        background_tasks.add_task(process_incoming_message, phone_number, text)
        return {"status": "processing_in_background"}

    return {"status": "unhandled_event"}

class NewLead(BaseModel):
    first_name: str
    phone_number: str
    model_interest: str

async def process_new_lead_outreach(lead: NewLead):
    digits = re.sub(r'\D', '', lead.phone_number)
    if len(digits) == 10:
        clean_phone = f"+1{digits}"
    elif len(digits) == 11 and digits.startswith("1"):
        clean_phone = f"+{digits}"
    else:
        clean_phone = lead.phone_number
        
    print(f"🚀 Processing new lead outreach for {clean_phone}")
    
    prompt = f"A new customer named {lead.first_name} just submitted a form on our website looking for pricing on the {lead.model_interest}. Write a highly friendly, 1-2 sentence opening SMS introducing yourself as Alex from Zebra Golf Cart and asking if they have any specific questions about it."
    
    ai_reply = await agent.generate_reply(clean_phone, prompt)
    
    media_url = None
    image_match = re.search(r"\[IMAGE:\s*(https?://[^\s\]]+)\]", ai_reply)
    if image_match:
        media_url = image_match.group(1)
        ai_reply = ai_reply.replace(image_match.group(0), "").strip()
        
    # Save to database BEFORE sending, so the webhook doesn't accidentally think a human sent it!
    database.save_message(clean_phone, "assistant", ai_reply)
    await quo.send_sms(clean_phone, ai_reply, media_url=media_url)

@app.post("/api/new-lead")
async def handle_new_lead(lead: NewLead, background_tasks: BackgroundTasks):
    background_tasks.add_task(process_new_lead_outreach, lead)
    return {"status": "outreach_started"}

@app.get("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
