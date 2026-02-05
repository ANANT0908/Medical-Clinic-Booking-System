from datetime import datetime
import random
from uuid import UUID
from sqlalchemy import text
from app.database import get_db
import json
import os
import asyncio
import base64
try:
    from google.cloud import pubsub_v1
except ImportError:
    pubsub_v1 = None

# ... (omitted)

    async def create_booking(self, transaction_id, data):
        # Generate reference ID
        ref_id = f"BK{datetime.now().strftime('%Y%m%d')}-{random.randint(100000,999999)}"
        
        # Create booking record
        await self.create_booking_record(transaction_id, ref_id, data)
        
        event_data = {
            "event_type": "booking.completed",
            "transaction_id": transaction_id,
            "timestamp": datetime.utcnow().isoformat(),
            "reference_id": ref_id
        }
        
        # Update local state so client sees it
        if os.getenv("PROJECT_ID") == "local-project":
            await self.update_state(transaction_id, "booking.completed", event_data)

        # Publish success
        await publish_event(event_data)

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
        
        # Compensate -> Quota Manager
        if event_type == "booking.compensate":
             target_url = "http://127.0.0.1:8083/"
             
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


class SagaCoordinator:
    async def handle_event(self, event: dict):
        event_type = event['event_type']
        transaction_id = event['transaction_id']
        
        # Update state
        await self.update_state(transaction_id, event_type, event)
        
        # Handle completion
        if event_type in ['booking.quota.acquired', 'booking.quota.skipped']:
            await self.create_booking(transaction_id, event['data'])
        
        # Handle failures
        elif event_type in ['booking.validation.failed', 'booking.quota.failed', 'booking.pricing.failed']:
            await self.handle_failure(transaction_id, event)

    def __init__(self):
        self._mock_db = {}

    def get_mock_status(self, transaction_id):
        return self._mock_db.get(str(transaction_id), {"current_state": "unknown", "events": []})

    async def update_state(self, transaction_id, event_type, event):
        if os.getenv("PROJECT_ID") == "local-project":
            tid = str(transaction_id)
            print(f"[MOCK DB] Saga State Update: {tid} -> {event_type}")
            if tid not in self._mock_db:
                self._mock_db[tid] = {"current_state": "initiated", "events": []}
            
            self._mock_db[tid]["current_state"] = event_type
            self._mock_db[tid]["events"].append({
                "event_type": event_type,
                "timestamp": datetime.utcnow().isoformat(),
                "data": event
            })
            return

        async with get_db() as db:
            # Upsert transaction state
            # Simple assumption: we just log the event in transaction_events and update state
            # For simplicity, just inserting event
            stmt_event = text("""
                INSERT INTO transaction_events (transaction_id, event_type, event_data)
                VALUES (:tid, :etype, :edata)
            """)
            await db.execute(stmt_event, {
                "tid": transaction_id,
                "etype": event_type,
                "edata": json.dumps(event)
            })
            
            # Update current state
            stmt_state = text("""
                INSERT INTO transaction_state (transaction_id, current_state)
                VALUES (:tid, :state)
                ON CONFLICT (transaction_id) 
                DO UPDATE SET current_state = :state, created_at = NOW()
            """)
            await db.execute(stmt_state, {
                "tid": transaction_id,
                "state": event_type
            })
            await db.commit()

    async def check_quota_allocation(self, transaction_id):
         if os.getenv("PROJECT_ID") == "local-project":
            tid = str(transaction_id)
            state = self._mock_db.get(tid)
            if state:
                for e in state["events"]:
                    if e["event_type"] == "booking.quota.acquired":
                        return True
            return False

         async with get_db() as db:
            stmt = text("SELECT COUNT(*) FROM quota_allocations WHERE transaction_id = :tid AND released = FALSE")
            result = await db.execute(stmt, {"tid": transaction_id})
            count = result.scalar()
            return count > 0

    async def handle_failure(self, transaction_id, event):
        # Check if quota was acquired
        quota_acquired = await self.check_quota_allocation(transaction_id)
        
        if quota_acquired:
            # Trigger compensation
            await publish_event({
                "event_type": "booking.compensate",
                "transaction_id": transaction_id,
                "timestamp": datetime.utcnow().isoformat(),
                "reason": event.get('error')
            })
            
    async def create_booking_record(self, transaction_id, ref_id, data):
         if os.getenv("PROJECT_ID") == "local-project":
            print(f"[MOCK DB] Booking Created! Ref: {ref_id}")
            return

         async with get_db() as db:
            stmt = text("""
                INSERT INTO bookings (
                    transaction_id, user_name, user_gender, user_dob, 
                    service_ids, base_price, discount_applied, 
                    discount_percentage, final_price, booking_status, reference_id
                ) VALUES (
                    :tid, :name, :gender, :dob, :sids, :bp, :da, :dp, :fp, :status, :ref
                )
            """)
            await db.execute(stmt, {
                "tid": transaction_id,
                "name": data.get('user_name'),
                "gender": data.get('user_gender'),
                # Parse DOB if it's a string, or rely on Postgres casting if simple format
                "dob": datetime.strptime(data.get('user_dob'), '%Y-%m-%d').date(), 
                "sids": data.get('service_ids'),
                "bp": data.get('base_price'),
                "da": data.get('discount_eligible', False),
                "dp": data.get('discount_percentage', 0.0),
                "fp": data.get('final_price'),
                "status": "confirmed",
                "ref": ref_id
            })
            await db.commit()

    async def create_booking(self, transaction_id, data):
        # Generate reference ID
        ref_id = f"BK{datetime.now().strftime('%Y%m%d')}-{random.randint(100000,999999)}"
        
        # Create booking record
        await self.create_booking_record(transaction_id, ref_id, data)
        
        event_data = {
            "event_type": "booking.completed",
            "transaction_id": transaction_id,
            "timestamp": datetime.utcnow().isoformat(),
            "reference_id": ref_id
        }

        # Update local state so client sees it
        if os.getenv("PROJECT_ID") == "local-project":
            await self.update_state(transaction_id, "booking.completed", event_data)
        
        # Publish success
        await publish_event(event_data)
