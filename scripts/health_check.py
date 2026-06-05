#!/usr/bin/env python3
"""SCPA Service Health Check — checks all endpoints
Run: python scripts/health_check.py
"""
import urllib.request
import json
import sys

SERVICES = [
    ("NCF Service", "http://localhost:8001/health"),
    ("SBERT Service", "http://localhost:8002/health"),
    ("DQN Service", "http://localhost:8003/health"),
    ("Hybrid Service", "http://localhost:8004/health"),
    ("API Gateway → NCF", "http://localhost:8000/api/ncf/health"),
    ("API Gateway → SBERT", "http://localhost:8000/api/sbert/health"),
    ("API Gateway → DQN", "http://localhost:8000/api/dqn/health"),
    ("API Gateway → Hybrid", "http://localhost:8000/api/hybrid/health"),
]

def check_health():
    errors = 0
    for name, url in SERVICES:
        try:
            req = urllib.request.Request(url, method='GET')
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
                status = data.get('status', 'unknown')
                print(f"✓ {name}: {status}")
        except Exception as e:
            print(f"✗ {name}: {e}")
            errors += 1

    print()
    if errors == 0:
        print(f"All {len(SERVICES)} services healthy")
        return 0
    else:
        print(f"{errors}/{len(SERVICES)} services unhealthy")
        return 1

if __name__ == "__main__":
    sys.exit(check_health())