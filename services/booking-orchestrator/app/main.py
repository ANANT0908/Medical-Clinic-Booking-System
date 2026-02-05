import base64
import json
import os
from fastapi import FastAPI, Request
from app.saga_coordinator import SagaCoordinator

app = FastAPI()
saga = SagaCoordinator()

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
    
    await saga.handle_event(event)
        
    return {"status": "processed"}

@app.get("/bookings/{transaction_id}")
async def get_booking_status(transaction_id: str):
    return saga.get_mock_status(transaction_id)
