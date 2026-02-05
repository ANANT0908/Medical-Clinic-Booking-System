import asyncio
import os
import sys
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
import httpx

console = Console()

API_URL = os.getenv("API_URL", "http://localhost:8080/api/v1")

async def get_services():
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{API_URL}/services")
            resp.raise_for_status()
            return resp.json()["services"]
        except Exception as e:
            console.print(f"[bold red]Error fetching services: {e}[/bold red]")
            return []

async def create_booking(data):
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{API_URL}/bookings", json=data)
            resp.raise_for_status()
            return resp.json()["transaction_id"]
        except Exception as e:
            console.print(f"[bold red]Error creating booking: {e}[/bold red]")
            sys.exit(1)

async def get_status(transaction_id):
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{API_URL}/bookings/{transaction_id}/status")
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"current_state": "unknown", "events": [], "error": str(e)}

async def get_booking(transaction_id):
    # In a real app this might be a separate endpoint or part of status
    # For now utilizing status endpoint data or assuming an endpoint exists if confirmed
    # Since spec didn't strictly define GET /bookings/{id}, we might need to rely on status.
    # However, the CLI code in spec has `booking = await get_booking(transaction_id)`
    # I will assume `get_status` returns enough info or I'll just use status for now.
    # Actually, let's mock the "booking details" fetch by reusing status info or assume
    # there is an endpoint. The API Gateway I wrote only has `get_status`, so I will just return status data.
    return await get_status(transaction_id)


# Event Mapping
EVENT_MAP = {
    "booking.initiated": ("BOOKING_REQUESTED", "Request received", "cyan"),
    "booking.validated": ("USER_VALIDATED", "User profile validated", "blue"),
    "booking.validation.failed": ("VALIDATION_FAILED", "Validation failed", "red"),
    "booking.priced": ("BASE_PRICE_CALCULATED", "Price calculated", "yellow"),
    "booking.pricing.failed": ("PRICING_FAILED", "Pricing calculation failed", "red"),
    "booking.quota.acquired": ("QUOTA_ACQUIRED", "Slot reserved", "green"),
    "booking.quota.skipped": ("DISCOUNT_SKIPPED", "R1 not applicable", "dim white"),
    "booking.quota.failed": ("QUOTA_FULL", "No slots available", "red"),
    "booking.quota.released": ("QUOTA_RELEASED", "Slot released", "yellow"),
    "booking.completed": ("BOOKING_CONFIRMED", "Booking persisted", "bold green"),
    "booking.compensate": ("COMPENSATING", "Rolling back transaction", "orange1"),
    "booking.failed": ("BOOKING_FAILED", "Transaction failed", "bold red")
}

def create_panel(events):
    table = Table(title="Transaction Events", expand=True)
    table.add_column("Time", style="cyan", no_wrap=True)
    table.add_column("Event", style="magenta")
    table.add_column("Info", style="green")

    for event in events:
        # Parse timestamp
        raw_ts = event.get("timestamp", "")
        try:
             # Try to format time only HH:MM:SS
             ts_obj = datetime.fromisoformat(raw_ts.replace('Z', '+00:00'))
             ts = ts_obj.strftime("%H:%M:%S")
        except:
             ts = raw_ts

        etype = event.get("event_type", "")
        
        # Get mapped values
        display_name, desc, color = EVENT_MAP.get(etype, (etype, "", "white"))
        
        info = desc
        # Special handling for pricing to show base price and then discount as separate row
        if etype == "booking.priced":
            data = event.get('data', {}).get('data', {})
            price = data.get('base_price')
            final_price = data.get('final_price')
            eligible = data.get('discount_eligible')
            pct = data.get('discount_percentage')
            reason = data.get('discount_reason') or desc
            
            # Row for base price
            table.add_row(ts, f"[{color}]{display_name}[/{color}]", f"Base price: ₹{price}")
            
            # Additional row if discount applied
            if eligible:
                table.add_row(ts, "[bold yellow]DISCOUNT_APPLIED[/bold yellow]", f"{reason}: {pct}% off (Final: ₹{final_price})")
            continue

        if etype == "booking.completed":
             # Extract ref and show it
             data = event.get('data', {})
             ref = data.get('reference_id')
             if ref:
                 info = f"Reference ID: {ref}"
        
        if "reason" in event:
            info = f"{desc} - Reason: {event['reason']}"
        elif "errors" in event:
            error_msg = ", ".join(event['errors']) if isinstance(event['errors'], list) else str(event['errors'])
            info = f"Errors: {error_msg}"
        elif "error" in event:
            info = f"Error: {event['error']}"
        
        table.add_row(ts, f"[{color}]{display_name}[/{color}]", info)
        
    return Panel(table, title="Booking Progress", border_style="blue")
    
# Add datetime import
from datetime import datetime

async def main():
    console.print("[bold green]Medical Clinic Booking System[/bold green]")
    
    # Get user input
    name = console.input("Name: ")
    gender = console.input("Gender (male/female): ")
    dob = console.input("DOB (YYYY-MM-DD): ")
    
    # Show services
    with console.status("Fetching services..."):
        services = await get_services()
    
    if not services:
        return

    table = Table(title="Available Services")
    table.add_column("ID", justify="right")
    table.add_column("Name")
    table.add_column("Price")
    
    for s in services:
        table.add_row(str(s['id']), s['name'], f"₹{s['base_price']}")
    
    console.print(table)
    
    service_ids_str = console.input("Service IDs (comma-separated): ")
    service_ids = [int(x.strip()) for x in service_ids_str.split(',') if x.strip()]
    
    # Create booking
    with console.status("Initiating booking..."):
        transaction_id = await create_booking({
            "user_name": name,
            "user_gender": gender,
            "user_dob": dob,
            "service_ids": service_ids
        })
    
    console.print(f"Booking initiated. ID: [bold]{transaction_id}[/bold]")
    
    # Monitor with real-time updates
    await monitor_booking(transaction_id)

async def monitor_booking(transaction_id):
    with Live(console=console, refresh_per_second=4) as live:
        while True:
            status = await get_status(transaction_id)
            live.update(create_panel(status['events']))
            
            current_state = status.get('current_state')
            if current_state in ['booking.completed', 'booking.quota.released', 'booking.failed']:
                break
            
            await asyncio.sleep(0.5)
    
    status = await get_status(transaction_id)
    # Show final result logic
    if status.get('current_state') == 'booking.completed':
        events = status.get('events', [])
        ref_id = "UNKNOWN"
        final_price = "UNKNOWN"
        for e in events:
            if e.get('event_type') == 'booking.completed':
                event_payload = e.get('data', {})
                ref_id = event_payload.get('reference_id')
            
            if e.get('event_type') == 'booking.priced':
                event_payload = e.get('data', {})
                inner_data = event_payload.get('data', {})
                final_price = inner_data.get('final_price')
                
        console.print("\n[bold green]Booking Successful ✅[/bold green]")
        console.print(f"Reference ID: {ref_id}")
        if final_price != "UNKNOWN":
            console.print(f"Final Amount: ₹{final_price}")
    else:
        last_error = "Unknown error"
        if status.get('events'):
            last_error = status['events'][-1].get('error', 'Failure')
        console.print(f"\n[bold red]✗ Failed: {last_error}[/bold red]")

if __name__ == "__main__":
    asyncio.run(main())
