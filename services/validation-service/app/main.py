import base64
import json
import os
from datetime import datetime
from fastapi import FastAPI, Request
try:
    from google.cloud import pubsub_v1
except ImportError:
    pubsub_v1 = None
import asyncio

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

async def publish_event(event_data: dict):
    if PROJECT_ID == "local-project":
        print(f"Mock Publish (Local): {json.dumps(event_data, indent=2)}", flush=True)
        event_type = event_data.get("event_type")
        target_url = None
        
        if event_type == "booking.validation.failed":
             target_url = "http://127.0.0.1:8084/"
        elif event_type == "booking.validated":
             target_url = "http://127.0.0.1:8082/"
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


async def get_services_by_ids(service_ids: list):
    # Mock data - ideally shares a common lib or calls a DB
    all_services = {
        1: {'id': 1, 'name': 'General Consultation', 'gender': 'both', 'base_price': 300.00},
        2: {'id': 2, 'name': 'Gynecology', 'gender': 'female', 'base_price': 500.00},
        3: {'id': 3, 'name': 'Ultrasound', 'gender': 'female', 'base_price': 800.00},
        4: {'id': 4, 'name': 'Blood Test', 'gender': 'both', 'base_price': 450.00},
        5: {'id': 5, 'name': 'Cardiology', 'gender': 'both', 'base_price': 600.00},
        6: {'id': 6, 'name': 'Urology', 'gender': 'male', 'base_price': 550.00},
        7: {'id': 7, 'name': 'Prostate Screening', 'gender': 'male', 'base_price': 700.00},
        8: {'id': 8, 'name': 'Dermatology', 'gender': 'both', 'base_price': 400.00},
    }
    # Return objects with dot notation access to match spec code
    class ServiceObj:
        def __init__(self, d):
            self.__dict__ = d
    return [ServiceObj(all_services[sid]) for sid in service_ids if sid in all_services]

@app.post("/")
async def receive_event(request: Request):
    """
    Receives Pub/Sub push messages.
    Format: {"message": {"data": "base64...", "attributes": {...}}}
    """
    body = await request.json()
    if not body or "message" not in body:
        return {"status": "ignored"}
    
    # Decode message
    b64_data = body["message"]["data"]
    data_str = base64.b64decode(b64_data).decode("utf-8")
    event = json.loads(data_str)
    
    event_type = event.get("event_type")
    
    if event_type == "booking.initiated":
        await handle_booking_initiated(event)
        
    return {"status": "processed"}

async def handle_booking_initiated(event: dict):
    print(f"Processing event: {event}")
    transaction_id = event['transaction_id']
    data = event['data']
    
    # Validate user data
    errors = []
    
    if not data.get('user_name'):
        errors.append("Name required")
    
    if data.get('user_gender') not in ['male', 'female']:
        errors.append("Invalid gender")
    
    # Validate services exist and match gender
    services = await get_services_by_ids(data['service_ids'])
    user_gender = data['user_gender']
    
    for svc in services:
        if svc.gender not in [user_gender, 'both']:
            errors.append(f"Service '{svc.name}' not available for {user_gender}")
    
    # Publish result
    if errors:
        result_event = {
            "event_type": "booking.validation.failed",
            "transaction_id": transaction_id,
            "timestamp": datetime.utcnow().isoformat(),
            "errors": errors
        }
        await publish_event(result_event)
    else:
        result_event = {
            "event_type": "booking.validated",
            "transaction_id": transaction_id,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data
        }
        await publish_event(result_event)
