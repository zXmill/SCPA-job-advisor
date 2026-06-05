"""Health check all SCPA services."""
import urllib.request
import json

services = [
    ("NCF",    8001),
    ("SBERT",  8002),
    ("DQN",    8003),
    ("Hybrid", 8004),
]

print("=== SCPA Health Check ===")
all_ok = True
for name, port in services:
    try:
        resp = urllib.request.urlopen(f"http://localhost:{port}/health", timeout=5)
        data = json.loads(resp.read())
        status = data.get("status", "unknown")
        print(f"  {name:8s} :{port}  ->  {status.upper()}")
    except Exception as e:
        print(f"  {name:8s} :{port}  ->  FAILED ({e})")
        all_ok = False

print("=" * 30)
print("Result:", "ALL OK" if all_ok else "SOME FAILED")
