#!/usr/bin/env python3
"""
Seed script: Load generated raw JSON datasets into the database (Prisma).

Usage examples:
  python -m app.scripts.seed_raw_from_generated --input-dir ../../data/generated_data --batch-size 500
  python -m app.scripts.seed_raw_from_generated --datasets products customers orders collections events

It expects JSON files in --input-dir:
  - raw_products.json
  - raw_customers.json
  - raw_orders.json
  - raw_collections.json
  - raw_behavioral_events.json
"""

import asyncio
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core.database import get_database, close_database
from app.core.logging import get_logger
from prisma import Json


logger = get_logger(__name__)


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        # Support both naive and Z-terminated strings
        if value.endswith("Z"):
            value = value.replace("Z", "+00:00")
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _load_json_array(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        logger.warning(f"File not found, skipping: {path}")
        return []
    with open(path, "r") as f:
        try:
            data = json.load(f)
            if not isinstance(data, list):
                logger.warning(
                    f"Expected a JSON array in {path}; got {type(data)}. Skipping."
                )
                return []
            return data
        except Exception as e:
            logger.error(f"Failed to read {path}: {e}")
            return []


async def _insert_in_batches(
    model, records: List[Dict[str, Any]], batch_size: int
) -> int:
    total = 0
    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        if not batch:
            continue
        # Use create_many with skip_duplicates to be idempotent
        await model.create_many(data=batch, skip_duplicates=True)
        total += len(batch)
    return total


async def seed_products(input_dir: str, batch_size: int) -> int:
    db = await get_database()
    path = os.path.join(input_dir, "raw_products.json")
    raw = _load_json_array(path)
    if not raw:
        return 0
    prepared: List[Dict[str, Any]] = []
    for r in raw:
        prepared.append(
            {
                # Allow explicit id if present
                **({"id": r.get("id")} if r.get("id") else {}),
                "shopId": r["shopId"],
                "payload": Json(r["payload"]),
                "shopifyId": r.get("shopifyId"),
                "shopifyCreatedAt": _parse_dt(r.get("shopifyCreatedAt")),
                "shopifyUpdatedAt": _parse_dt(r.get("shopifyUpdatedAt")),
                "extractedAt": _parse_dt(r.get("extractedAt")),
            }
        )
    inserted = await _insert_in_batches(db.rawproduct, prepared, batch_size)
    logger.info(f"Inserted products: {inserted}")
    return inserted


async def seed_customers(input_dir: str, batch_size: int) -> int:
    db = await get_database()
    path = os.path.join(input_dir, "raw_customers.json")
    raw = _load_json_array(path)
    if not raw:
        return 0
    prepared: List[Dict[str, Any]] = []
    for r in raw:
        prepared.append(
            {
                **({"id": r.get("id")} if r.get("id") else {}),
                "shopId": r["shopId"],
                "payload": Json(r["payload"]),
                "shopifyId": r.get("shopifyId"),
                "shopifyCreatedAt": _parse_dt(r.get("shopifyCreatedAt")),
                "shopifyUpdatedAt": _parse_dt(r.get("shopifyUpdatedAt")),
                "extractedAt": _parse_dt(r.get("extractedAt")),
            }
        )
    inserted = await _insert_in_batches(db.rawcustomer, prepared, batch_size)
    logger.info(f"Inserted customers: {inserted}")
    return inserted


async def seed_orders(input_dir: str, batch_size: int) -> int:
    db = await get_database()
    path = os.path.join(input_dir, "raw_orders.json")
    raw = _load_json_array(path)
    if not raw:
        return 0
    prepared: List[Dict[str, Any]] = []
    for r in raw:
        prepared.append(
            {
                **({"id": r.get("id")} if r.get("id") else {}),
                "shopId": r["shopId"],
                "payload": Json(r["payload"]),
                "shopifyId": r.get("shopifyId"),
                "shopifyCreatedAt": _parse_dt(r.get("shopifyCreatedAt")),
                "shopifyUpdatedAt": _parse_dt(r.get("shopifyUpdatedAt")),
                "extractedAt": _parse_dt(r.get("extractedAt")),
            }
        )
    inserted = await _insert_in_batches(db.raworder, prepared, batch_size)
    logger.info(f"Inserted orders: {inserted}")
    return inserted


async def seed_collections(input_dir: str, batch_size: int) -> int:
    db = await get_database()
    path = os.path.join(input_dir, "raw_collections.json")
    raw = _load_json_array(path)
    if not raw:
        return 0
    prepared: List[Dict[str, Any]] = []
    for r in raw:
        prepared.append(
            {
                **({"id": r.get("id")} if r.get("id") else {}),
                "shopId": r["shopId"],
                "payload": Json(r["payload"]),
                "shopifyId": r.get("shopifyId"),
                "shopifyCreatedAt": _parse_dt(r.get("shopifyCreatedAt")),
                "shopifyUpdatedAt": _parse_dt(r.get("shopifyUpdatedAt")),
                "extractedAt": _parse_dt(r.get("extractedAt")),
            }
        )
    inserted = await _insert_in_batches(db.rawcollection, prepared, batch_size)
    logger.info(f"Inserted collections: {inserted}")
    return inserted


async def seed_behavioral_events(input_dir: str, batch_size: int) -> int:
    db = await get_database()
    path = os.path.join(input_dir, "raw_behavioral_events.json")
    raw = _load_json_array(path)
    if not raw:
        return 0
    prepared: List[Dict[str, Any]] = []
    for r in raw:
        prepared.append(
            {
                **({"id": r.get("id")} if r.get("id") else {}),
                "shopId": r["shopId"],
                "payload": Json(r["payload"]),
                "receivedAt": _parse_dt(r.get("receivedAt")),
            }
        )
    inserted = await _insert_in_batches(db.rawbehavioralevents, prepared, batch_size)
    logger.info(f"Inserted behavioral events: {inserted}")
    return inserted


async def main_async(input_dir: str, batch_size: int, datasets: List[str]):
    inserted_counts: Dict[str, int] = {}

    try:
        if "products" in datasets:
            inserted_counts["products"] = await seed_products(input_dir, batch_size)
        if "customers" in datasets:
            inserted_counts["customers"] = await seed_customers(input_dir, batch_size)
        if "orders" in datasets:
            inserted_counts["orders"] = await seed_orders(input_dir, batch_size)
        if "collections" in datasets:
            inserted_counts["collections"] = await seed_collections(
                input_dir, batch_size
            )
        if "events" in datasets:
            inserted_counts["events"] = await seed_behavioral_events(
                input_dir, batch_size
            )

        total = sum(inserted_counts.values())
        logger.info(
            f"Seed complete. Inserted total records: {total} | Breakdown: {inserted_counts}"
        )
    finally:
        await close_database()


def parse_args():
    import argparse

    parser = argparse.ArgumentParser(
        description="Seed raw tables from generated JSON data"
    )
    parser.add_argument(
        "--input-dir",
        default=os.path.abspath(
            os.path.join(os.path.dirname(__file__), "../../../data/generated_data")
        ),
        help="Directory containing raw_*.json files (default: data/generated_data)",
    )
    parser.add_argument(
        "--batch-size", type=int, default=500, help="Insert batch size (default: 500)"
    )
    parser.add_argument(
        "--datasets",
        nargs="*",
        choices=["products", "customers", "orders", "collections", "events"],
        default=["products", "customers", "orders", "collections", "events"],
        help="Datasets to seed (default: all)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    asyncio.run(main_async(args.input_dir, args.batch_size, args.datasets))


if __name__ == "__main__":
    main()
