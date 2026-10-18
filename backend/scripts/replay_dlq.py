#!/usr/bin/env python3
"""
Dead Letter Queue (DLQ) Management & Replay Tool
Allows inspecting, purging, and replaying failed events from the Dead Letter Queue.

Usage:
    python backend/scripts/replay_dlq.py status
    python backend/scripts/replay_dlq.py replay [--limit 50]
    python backend/scripts/replay_dlq.py purge
"""

import argparse
import json
import logging
import sys

from backend.events.event_bus import get_event_bus

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("dlq_tool")


def show_status():
    bus = get_event_bus()
    dlq_events = bus.get_dead_letter_events(limit=100)
    print(f"\n=== Dead Letter Queue (DLQ) Status ===")
    print(f"Total failed events visible: {len(dlq_events)}")
    if not dlq_events:
        print("DLQ is empty. No failed events recorded.")
        return

    for i, item in enumerate(dlq_events, start=1):
        print(f"\n[{i}] Event ID: {item.get('event_id')} | Type: {item.get('event_type')}")
        print(f"    Failed At: {item.get('failed_at')}")
        print(f"    Handler:   {item.get('handler')}")
        print(f"    Error:     {item.get('error')}")
        print(f"    Retries:   {item.get('retry_count')}")


def replay_events(limit: int):
    bus = get_event_bus()
    print(f"\nReplaying up to {limit} DLQ events...")
    result = bus.replay_dead_letter_events(limit=limit)
    print(f"\nReplay summary:")
    print(f"  Successfully replayed: {result.get('replayed')}")
    print(f"  Still failing:         {result.get('still_failing')}")
    print(f"  Remaining in DLQ:      {result.get('remaining')}")


def purge_queue():
    bus = get_event_bus()
    count = bus.purge_dead_letter_queue()
    print(f"\nPurged {count} events from Dead Letter Queue.")


def main():
    parser = argparse.ArgumentParser(description="Manage and replay events in the Dead Letter Queue (DLQ).")
    subparsers = parser.add_subparsers(dest="action", required=True)

    subparsers.add_parser("status", help="Display current DLQ entries")

    replay_parser = subparsers.add_parser("replay", help="Replay failed DLQ events")
    replay_parser.add_argument("--limit", type=int, default=50, help="Maximum number of events to replay")

    subparsers.add_parser("purge", help="Purge all entries from the DLQ")

    args = parser.parse_args()

    if args.action == "status":
        show_status()
    elif args.action == "replay":
        replay_events(args.limit)
    elif args.action == "purge":
        purge_queue()


if __name__ == "__main__":
    main()
