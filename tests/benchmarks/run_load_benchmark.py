#!/usr/bin/env python3
"""
Tier 2 server load benchmark: concurrent POST /api/v1/tickets/parse requests.

Usage (server must be running on localhost:8000):
  uv run python tests/benchmarks/run_load_benchmark.py --concurrency 3 --payload fifty

Append results to benchmark.md manually or via --json-out results.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

import httpx

PAYLOADS = {
    "single": "tests/payloads/single_ticket_hardware_battery_drain.json",
    "twenty_five": "tests/payloads/twenty_five_tickets_mixed.json",
    "fifty": "tests/payloads/fifty_tickets_mixed.json",
}


async def run_one(client: httpx.AsyncClient, payload_path: Path) -> dict:
    body = json.loads(payload_path.read_text())
    start = time.perf_counter()
    resp = await client.post("/api/v1/tickets/parse", json=body)
    wall = time.perf_counter() - start
    data = resp.json() if resp.status_code == 200 else {}
    tickets = len(body.get("tickets", []))
    duration = data.get("duration_seconds") or wall
    return {
        "status_code": resp.status_code,
        "tickets": tickets,
        "duration_seconds": duration,
        "wall_seconds": wall,
        "success_count": data.get("success_count", 0),
        "failure_count": data.get("failure_count", 0),
        "estimated_batch_count": (data.get("processing_estimate") or {}).get("estimated_batch_count"),
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Tier 2 concurrent load benchmark")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--payload", choices=list(PAYLOADS.keys()), default="fifty")
    parser.add_argument("--json-out", type=str, default="")
    args = parser.parse_args()

    payload_path = Path(PAYLOADS[args.payload])
    if not payload_path.is_file():
        raise SystemExit(f"Payload not found: {payload_path}")

    async with httpx.AsyncClient(base_url=args.base_url, timeout=600.0) as client:
        start = time.perf_counter()
        results = await asyncio.gather(
            *[run_one(client, payload_path) for _ in range(args.concurrency)]
        )
        total_wall = time.perf_counter() - start

    total_tickets = sum(r["tickets"] for r in results)
    report = {
        "tier": 2,
        "concurrency": args.concurrency,
        "payload": args.payload,
        "total_wall_seconds": total_wall,
        "aggregate_throughput_tickets_per_sec": total_tickets / total_wall if total_wall else 0,
        "per_request": results,
    }
    print(json.dumps(report, indent=2))
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
