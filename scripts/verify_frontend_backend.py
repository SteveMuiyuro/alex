#!/usr/bin/env python3
"""
Lightweight connectivity checks between frontend origin and backend API.

Usage:
  uv run scripts/verify_frontend_backend.py --api-url https://alex-api-xxxx.run.app --origin https://storage.googleapis.com/my-bucket
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


def request(method: str, url: str, headers: dict[str, str] | None = None) -> tuple[int, dict[str, str], str]:
    req = urllib.request.Request(url=url, method=method, headers=headers or {})
    with urllib.request.urlopen(req, timeout=20) as response:
        body = response.read().decode("utf-8")
        return response.status, dict(response.headers), body


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", required=True, help="Cloud Run API base URL (e.g. https://alex-api-xyz.a.run.app)")
    parser.add_argument("--origin", required=True, help="Frontend origin to test CORS (e.g. https://storage.googleapis.com/my-bucket)")
    args = parser.parse_args()

    api_url = args.api_url.rstrip("/")
    health_url = f"{api_url}/health"
    user_url = f"{api_url}/api/user"

    print(f"Checking health endpoint: {health_url}")
    try:
        status, _, body = request("GET", health_url)
        payload = json.loads(body)
        print(f"✅ /health status={status} payload={payload}")
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
        print(f"❌ /health check failed: {exc}")
        return 1

    print(f"Checking CORS preflight for origin={args.origin}")
    try:
        status, headers, _ = request(
            "OPTIONS",
            user_url,
            headers={
                "Origin": args.origin,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )
        allow_origin = headers.get("Access-Control-Allow-Origin", "")
        allow_methods = headers.get("Access-Control-Allow-Methods", "")
        if status in (200, 204) and allow_origin in (args.origin, "*"):
            print(f"✅ CORS preflight status={status} allow-origin={allow_origin} allow-methods={allow_methods}")
            return 0
        print(f"❌ Unexpected CORS response status={status} allow-origin={allow_origin} allow-methods={allow_methods}")
        return 1
    except urllib.error.HTTPError as exc:
        print(f"❌ CORS preflight failed: HTTP {exc.code} {exc.reason}")
        return 1
    except urllib.error.URLError as exc:
        print(f"❌ CORS preflight failed: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
