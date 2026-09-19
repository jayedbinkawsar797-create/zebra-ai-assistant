import os
import re
import uvicorn
import asyncio
from fastapi import FastAPI, Request, BackgroundTasks
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
    # 1. Ask AI for reply
    ai_reply = await agent.generate_reply(from_number, text)
    
    # 2. Handle Stop/Handoff
    if "[STOP]" in ai_reply:
        database.pause_ai_for_lead(from_number)
        return
        
    if "[HUMAN_TAKEOVER]" in ai_reply:
        database.pause_ai_for_lead(from_number)
        handoff_msg = "I'd be happy to schedule a call with one of our specialists. I'll have them reach out to you shortly!"
        database.save_message(from_number, "assistant", handoff_msg)
        await quo.send_sms(from_number, handoff_msg)
        return

    # 3. Extract Image Tag if present
    media_url = None
    image_match = re.search(r"\[IMAGE:\s*(https?://[^\s\]]+)\]", ai_reply)
    if image_match:
        media_url = image_match.group(1)
        ai_reply = ai_reply.replace(image_match.group(0), "").strip()
        
    # 4. Human Typing Delay
    # Calculates a delay based on message length (e.g., 20 chars per second), min 4s, max 12s
    typing_delay = min(12, max(4, len(ai_reply) / 20))
    await asyncio.sleep(typing_delay)
    
    # 5. Save and send
    database.save_message(from_number, "assistant", ai_reply)
    await quo.send_sms(from_number, ai_reply, media_url=media_url)

@app.post("/webhooks/quo")
async def handle_quo_webhook(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    
    if payload.get("type") == "message.received":
        data = payload.get("data", {})
        direction = data.get("direction")
        
        if direction != "incoming":
            sender_id = data.get("userId") 
            if sender_id and sender_id != "ai_system":
                phone_number = data.get("to", [""])[0]
                database.pause_ai_for_lead(phone_number)
                print(f"🛑 Human takeover detected for {phone_number}. AI paused.")
            return {"status": "ignored_outgoing"}
            
        from_number = data.get("from")
        text = data.get("content", "")
        
        lead = database.get_lead(from_number)
        if lead and lead.get("ai_paused"):
            return {"status": "ai_paused"}
            
        # Save user message immediately so it's in the DB
        database.save_message(from_number, "user", text)
        
        # Send processing to background task so Quo gets a 200 OK instantly and doesn't timeout!
        background_tasks.add_task(process_incoming_message, from_number, text)
        return {"status": "processing_in_background"}

    return {"status": "unhandled_event"}

@app.get("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
