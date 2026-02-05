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
from app.pricing_engine import PricingEngine

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

pricing_engine = PricingEngine()

async def publish_event(event_data: dict):
    if PROJECT_ID == "local-project":
        print(f"Mock Publish (Local): {json.dumps(event_data, indent=2)}", flush=True)
        event_type = event_data.get("event_type")
        target_url = None
        
        if event_type == "booking.pricing.failed":
             target_url = "http://127.0.0.1:8084/"
        elif event_type == "booking.priced":
             target_url = "http://127.0.0.1:8083/"
             # Also send to Orchestrator for tracking
             asyncio.create_task(send_local_event("http://127.0.0.1:8084/", event_data))
             
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
    
    if event_type == "booking.validated":
        await handle_booking_validated(event)
        
    return {"status": "processed"}

async def handle_booking_validated(event: dict):
    print(f"Processing event: {event}")
    transaction_id = event['transaction_id']
    data = event['data']
    
    try:
        pricing_result = await pricing_engine.calculate(data)
        
        # Merge pricing result into data
        data.update(pricing_result)
        
        result_event = {
            "event_type": "booking.priced",
            "transaction_id": transaction_id,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data
        }
        await publish_event(result_event)
    except Exception as e:
        import traceback
        print(f"Pricing failed: {e}", flush=True)
        traceback.print_exc()
        error_event = {
            "event_type": "booking.pricing.failed",
            "transaction_id": transaction_id,
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }
        await publish_event(error_event)
