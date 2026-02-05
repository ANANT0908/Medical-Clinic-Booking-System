import base64
import json
import os
import asyncio
from fastapi import FastAPI, Request
try:
    from google.cloud import pubsub_v1
except ImportError:
    pubsub_v1 = None
from datetime import datetime
from uuid import UUID
from app.quota_manager import QuotaManager

app = FastAPI()

# Configuration
PROJECT_ID = os.getenv("PROJECT_ID", "local-project")
TOPIC_ID = os.getenv("TOPIC_ID", "booking-events")

# Pub/Sub Publisher
if pubsub_v1:
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)
else:
    publisher = None
    topic_path = None

quota_manager = QuotaManager()

async def publish_event(event_data: dict):
    if PROJECT_ID == "local-project":
        print(f"Mock Publish (Local): {json.dumps(event_data, indent=2)}", flush=True)
        event_type = event_data.get("event_type")
        target_url = None
        
        # Quota outcomes go to Orchestrator
        if event_type in ["booking.quota.acquired", "booking.quota.skipped", "booking.quota.failed", "booking.quota.released"]:
             target_url = "http://127.0.0.1:8084/"
             
        if target_url:
            import httpx
            asyncio.create_task(send_local_event(target_url, event_data))
        return
        
    data_str = json.dumps(event_data)
    data_bytes = data_str.encode("utf-8")
    future = publisher.publish(
        topic_path, 
        data_bytes, 
        event_type=event_data.get("event_type", "unknown"),
        transaction_id=event_data.get("transaction_id", "")
    )
    future.result()

async def send_local_event(url, data):
    import httpx
    try:
        # Simulate Pub/Sub message format
        payload = {
            "message": {
                "data": base64.b64encode(json.dumps(data).encode("utf-8")).decode("utf-8"),
                "attributes": {
                    "event_type": data.get("event_type")
                }
            }
        }
        async with httpx.AsyncClient() as client:
            await client.post(url, json=payload)
    except Exception as e:
        print(f"Failed to send local event to {url}: {e}")


@app.post("/")
async def receive_event(request: Request):
    """
    Receives Pub/Sub push messages.
    """
    body = await request.json()
    if not body or "message" not in body:
        return {"status": "ignored"}
    
    # Decode message
    b64_data = body["message"]["data"]
    data_str = base64.b64decode(b64_data).decode("utf-8")
    event = json.loads(data_str)
    
    event_type = event.get("event_type")
    
    if event_type == "booking.priced":
        await handle_booking_priced(event)
    elif event_type == "booking.compensate":
        await handle_compensation(event)
        
    return {"status": "processed"}

async def handle_booking_priced(event: dict):
    print(f"Processing event: {event}")
    data = event['data']
    
    # Check if discount eligible
    if not data.get('discount_eligible'):
        # Skip quota check
        await publish_event({
            "event_type": "booking.quota.skipped",
            "transaction_id": event['transaction_id'],
            "timestamp": datetime.utcnow().isoformat(),
            "data": data
        })
        return
    
    # Acquire quota
    transaction_id = UUID(event['transaction_id'])
    acquired, message = await quota_manager.acquire_quota(transaction_id)
    
    if acquired:
        await publish_event({
            "event_type": "booking.quota.acquired",
            "transaction_id": event['transaction_id'],
            "timestamp": datetime.utcnow().isoformat(),
            "data": data
        })
    else:
        await publish_event({
            "event_type": "booking.quota.failed",
            "transaction_id": event['transaction_id'],
            "timestamp": datetime.utcnow().isoformat(),
            "error": message
        })

async def handle_compensation(event: dict):
    """Handle compensation request"""
    print(f"Compensating event: {event}")
    transaction_id = UUID(event['transaction_id'])
    released = await quota_manager.release_quota(transaction_id)
    
    if released:
        await publish_event({
            "event_type": "booking.quota.released",
            "transaction_id": event['transaction_id'],
            "timestamp": datetime.utcnow().isoformat()
        })
