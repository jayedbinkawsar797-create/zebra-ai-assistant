import os
import uvicorn
from fastapi import FastAPI, Request
from dotenv import load_dotenv

import database
import quo
import agent

load_dotenv()

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    database.init_db()

@app.post("/webhooks/quo")
async def handle_quo_webhook(request: Request):
    payload = await request.json()
    
    # Check if this is an incoming message event
    if payload.get("type") == "message.received":
        data = payload.get("data", {})
        direction = data.get("direction")
        
        # WE ONLY PROCESS INCOMING MESSAGES
        if direction != "incoming":
            # This is an outgoing message. Did a human rep send it?
            sender_id = data.get("userId") # Quo user id of human rep
            if sender_id and sender_id != "ai_system": # Replace with actual logic
                # A human took over! Pause AI.
                phone_number = data.get("to", [""])[0]
                database.pause_ai_for_lead(phone_number)
                print(f"🛑 Human takeover detected for {phone_number}. AI paused.")
            return {"status": "ignored_outgoing"}
            
        from_number = data.get("from")
        text = data.get("content", "")
        
        print(f"📩 New message from {from_number}: {text}")
        
        # Check if AI is paused for this lead
        lead = database.get_lead(from_number)
        if lead and lead.get("ai_paused"):
            print(f"⏸️ AI is paused for {from_number}. Ignoring.")
            return {"status": "ai_paused"}
            
        # 1. Save incoming message to history
        database.save_message(from_number, "user", text)
        
        # 2. Get AI Response
        ai_reply = await agent.generate_reply(from_number, text)
        
        # 3. Handle special flags
        if "[STOP]" in ai_reply:
            database.pause_ai_for_lead(from_number)
            print(f"🛑 Customer opted out: {from_number}")
            return {"status": "opted_out"}
            
        if "[HUMAN_TAKEOVER]" in ai_reply:
            database.pause_ai_for_lead(from_number)
            handoff_msg = "I'd be happy to schedule a call with one of our specialists. I'll have them reach out to you shortly!"
            database.save_message(from_number, "assistant", handoff_msg)
            await quo.send_sms(from_number, handoff_msg)
            # You could add logic here to notify your sales reps (e.g. Slack/Email alert)
            return {"status": "human_takeover_triggered"}
            
        # 4. Save and send normal AI reply
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
