import asyncio
import database
import quo
import agent

async def run_followup_job():
    print("🔄 Running 24-hour follow-up check...")
    leads = database.get_leads_needing_followup()
    
    for lead in leads:
        phone_number = lead["phone_number"]
        print(f"⏰ Sending 24h follow-up to {phone_number}")
        
        # Generate the follow-up text using AI
        prompt = "The customer hasn't replied in 24 hours. Write a short, friendly, 1-sentence follow-up message to check in on them and see if they have any questions about the golf carts."
        reply = await agent.generate_reply(phone_number, prompt)
        
        if "[STOP]" not in reply and "[HUMAN_TAKEOVER]" not in reply:
            await quo.send_sms(phone_number, reply)
            database.save_message(phone_number, "assistant", reply)
            database.increment_followup(phone_number)
        
    print("✅ Follow-up check complete.")

async def start_scheduler():
    while True:
        await run_followup_job()
        # Run every 1 hour (3600 seconds)
        await asyncio.sleep(3600)
