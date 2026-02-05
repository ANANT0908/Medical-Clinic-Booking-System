import subprocess
import os
import sys
import time

# Configuration
SERVICES = [
    ("services/api-gateway", 8080),
    ("services/validation-service", 8081),
    ("services/pricing-service", 8082),
    ("services/quota-manager", 8083),
    ("services/booking-orchestrator", 8084),
]

processes = []

def start_services():
    print("Starting services in LOCAL MODE (Access API at http://localhost:8080)...")
    
    # Common Env Vars
    env = os.environ.copy()
    env["PROJECT_ID"] = "local-project"
    env["TOPIC_ID"] = "booking-events"
    # No DB URL needed as we mocked it for local-project
    
    for path, port in SERVICES:
        print(f"Starting {path} on port {port}...")
        
        # Command: uvicorn app.main:app --host 0.0.0.0 --port PORT
        # We need to run this from the service directory or set pythonpath
        # Easier to cwd into the directory
        
        cmd = [sys.executable, "-u", "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)]
        
        # Start process
        p = subprocess.Popen(cmd, cwd=path, env=env, shell=False)
        processes.append((path, p))
        
    print("\nAll services started! Press Ctrl+C to stop.")

def stop_services():
    print("\nStopping services...")
    for name, p in processes:
        print(f"Terminating {name}...")
        p.terminate()
        
    print("Cleanup complete.")

if __name__ == "__main__":
    try:
        start_services()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_services()
