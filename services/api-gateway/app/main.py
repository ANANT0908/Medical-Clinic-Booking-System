from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from uuid import uuid4
from datetime import datetime
import os
import json
import base64
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

class BookingRequest(BaseModel):
    user_name: str
    user_gender: str  # 'male' or 'female'
    user_dob: str     # 'YYYY-MM-DD'
    service_ids: list[int]

async def publish_event(event_data: dict):
    if PROJECT_ID == "local-project":
        print(f"Mock Publish (Local): {json.dumps(event_data, indent=2)}", flush=True)
        # Local routing logic
        event_type = event_data.get("event_type")
        target_url = None
        
        if event_type == "booking.initiated":
            target_url = "http://127.0.0.1:8081/"
            # Also send to Orchestrator for tracking
            orchestrator_url = "http://127.0.0.1:8084/"
            asyncio.create_task(send_local_event(orchestrator_url, event_data))
            
        if target_url:
            import httpx
            # Async fire and forget (simulating pub/sub async nature)
            asyncio.create_task(send_local_event(target_url, event_data))
        else:
            print(f"Warning: No local route for {event_type}", flush=True)
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


async def get_transaction_state(transaction_id: str):
    # In a real implementation this would query the DB
    # For now returning mock
    return type('obj', (object,), {'current_state': 'processing'})()

async def get_transaction_events(transaction_id: str):
    # In a real implementation this would query the DB
    return []

async def get_services(gender: str = None):
    # Mock services response as per DB values for now, essentially acting as a cache or direct DB query
    # In full implementation, this connects to DB.
    # We will use the hardcoded list for simplicity unless user wants full DB connectivity code here immediately.
    # The spec has DB code in sections, but main.py provided in spec calls `get_services`.
    # I will stick to the provided `main.py` skeleton but fill in the gaps to make it runnable.
    all_services = [
        {'id': 1, 'name': 'General Consultation', 'gender': 'both', 'base_price': 300.00},
        {'id': 2, 'name': 'Gynecology', 'gender': 'female', 'base_price': 500.00},
        {'id': 3, 'name': 'Ultrasound', 'gender': 'female', 'base_price': 800.00},
        {'id': 4, 'name': 'Blood Test', 'gender': 'both', 'base_price': 450.00},
        {'id': 5, 'name': 'Cardiology', 'gender': 'both', 'base_price': 600.00},
        {'id': 6, 'name': 'Urology', 'gender': 'male', 'base_price': 550.00},
        {'id': 7, 'name': 'Prostate Screening', 'gender': 'male', 'base_price': 700.00},
        {'id': 8, 'name': 'Dermatology', 'gender': 'both', 'base_price': 400.00},
    ]
    if gender:
        return [s for s in all_services if s['gender'] in [gender, 'both']]
    return all_services

@app.post("/api/v1/bookings")
async def create_booking(request: BookingRequest):
    transaction_id = uuid4()
    
    event = {
        "event_type": "booking.initiated",
        "transaction_id": str(transaction_id),
        "timestamp": datetime.utcnow().isoformat(),
        "data": request.model_dump()
    }
    
    await publish_event(event)
    
    return {
        "transaction_id": str(transaction_id),
        "status": "initiated"
    }

@app.get("/api/v1/bookings/{transaction_id}/status")
async def get_status(transaction_id: str):
    if PROJECT_ID == "local-project":
        import httpx
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"http://127.0.0.1:8084/bookings/{transaction_id}")
                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "transaction_id": transaction_id,
                        "current_state": data.get("current_state"),
                        "events": data.get("events", [])
                    }
        except Exception as e:
            print(f"Failed to fetch local status: {e}")
            
    # Query transaction_state and transaction_events
    state = await get_transaction_state(transaction_id)
    events = await get_transaction_events(transaction_id)
    
    return {
        "transaction_id": transaction_id,
        "current_state": state.current_state,
        "events": events
    }

@app.get("/api/v1/services")
async def list_services(gender: str = None):
    services = await get_services(gender)
    return {"services": services}
