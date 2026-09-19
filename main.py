import os
import uvicorn
import asyncio
from fastapi import FastAPI, Request
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
    # Start the background follow-up scheduler
    asyncio.create_task(scheduler.start_scheduler())

@app.post("/webhooks/quo")
async def handle_quo_webhook(request: Request):
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
            
        database.save_message(from_number, "user", text)
        
        ai_reply = await agent.generate_reply(from_number, text)
        
        if "[STOP]" in ai_reply:
            database.pause_ai_for_lead(from_number)
            return {"status": "opted_out"}
            
        if "[HUMAN_TAKEOVER]" in ai_reply:
            database.pause_ai_for_lead(from_number)
            handoff_msg = "I'd be happy to schedule a call with one of our specialists. I'll have them reach out to you shortly!"
            database.save_message(from_number, "assistant", handoff_msg)
            await quo.send_sms(from_number, handoff_msg)
            return {"status": "human_takeover_triggered"}
            
        database.save_message(from_number, "assistant", ai_reply)
        await quo.send_sms(from_number, ai_reply)
        
        return {"status": "replied"}

    return {"status": "unhandled_event"}

@app.get("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
