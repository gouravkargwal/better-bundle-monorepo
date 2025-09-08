#!/usr/bin/env python3
"""
Main Data Generator - Orchestrates the generation of all test data
"""

import json
import asyncio
from datetime import datetime
from typing import List, Dict, Any

# Import all generators
from base_data_generator import BaseDataGenerator
from raw_products_generator import RawProductsGenerator
from raw_customers_generator import RawCustomersGenerator
from raw_orders_generator import RawOrdersGenerator
from raw_collections_generator import RawCollectionsGenerator
from raw_behavioral_events_generator import RawBehavioralEventsGenerator


class MainDataGenerator:
    """Main orchestrator for generating all test data"""

    def __init__(self):
        self.shops = [
            {
                "id": "shop_123",
                "name": "Fashion Store",
                "domain": "fashion-store.myshopify.com",
            },
            {
                "id": "shop_456",
                "name": "Electronics Hub",
                "domain": "electronics-hub.myshopify.com",
            },
            {
                "id": "shop_789",
                "name": "Home & Garden",
                "domain": "home-garden.myshopify.com",
            },
        ]

        # Data volume configuration
        self.data_volumes = {
            "small": {
                "products_per_shop": 50,
                "customers_per_shop": 100,
                "orders_per_shop": 200,
                "collections_per_shop": 10,
                "behavioral_events_per_shop": 1000,
            },
            "medium": {
                "products_per_shop": 200,
                "customers_per_shop": 500,
                "orders_per_shop": 1000,
                "collections_per_shop": 25,
                "behavioral_events_per_shop": 5000,
            },
            "large": {
                "products_per_shop": 500,
                "customers_per_shop": 1000,
                "orders_per_shop": 2000,
                "collections_per_shop": 50,
                "behavioral_events_per_shop": 10000,
            },
        }

        # Initialize generators
        self.products_generator = RawProductsGenerator()
        self.customers_generator = RawCustomersGenerator()
        self.orders_generator = RawOrdersGenerator()
        self.collections_generator = RawCollectionsGenerator()
        self.events_generator = RawBehavioralEventsGenerator()

    def generate_all_data(
        self, volume: str = "medium"
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Generate all test data for the specified volume"""

        if volume not in self.data_volumes:
            raise ValueError(
                f"Invalid volume: {volume}. Must be one of: {list(self.data_volumes.keys())}"
            )

        config = self.data_volumes[volume]
        print(f"🚀 Starting data generation with {volume} volume...")
        print(f"📊 Configuration: {config}")
        print(f"🏪 Shops: {len(self.shops)}")

        all_data = {}

        # Step 1: Generate Products (independent)
        print("\n📦 Generating products...")
        products = self.products_generator.generate_all_products(
            self.shops, config["products_per_shop"]
        )
        all_data["products"] = products
        print(f"✅ Generated {len(products)} products")

        # Step 2: Generate Customers (independent)
        print("\n👥 Generating customers...")
        customers = self.customers_generator.generate_all_customers(
            self.shops, config["customers_per_shop"]
        )
        all_data["customers"] = customers
        print(f"✅ Generated {len(customers)} customers")

        # Step 3: Generate Collections (independent)
        print("\n📚 Generating collections...")
        collections = self.collections_generator.generate_all_collections(
            self.shops, config["collections_per_shop"]
        )
        all_data["collections"] = collections
        print(f"✅ Generated {len(collections)} collections")

        # Step 4: Generate Orders (depends on customers and products)
        print("\n🛒 Generating orders...")
        orders = self.orders_generator.generate_all_orders(
            self.shops, customers, products, config["orders_per_shop"]
        )
        all_data["orders"] = orders
        print(f"✅ Generated {len(orders)} orders")

        # Step 5: Generate Behavioral Events (depends on customers and products)
        print("\n📊 Generating behavioral events...")
        events = self.events_generator.generate_all_behavioral_events(
            self.shops, customers, products, config["behavioral_events_per_shop"]
        )
        all_data["behavioral_events"] = events
        print(f"✅ Generated {len(events)} behavioral events")

        # Calculate totals
        total_records = sum(len(data) for data in all_data.values())
        print(f"\n🎉 Data generation complete!")
        print(f"📈 Total records generated: {total_records:,}")

        return all_data

    def save_data_to_files(
        self, data: Dict[str, List[Dict[str, Any]]], output_dir: str = "generated_data"
    ):
        """Save generated data to JSON files"""
        import os

        # Create output directory
        os.makedirs(output_dir, exist_ok=True)

        print(f"\n💾 Saving data to {output_dir}/...")

        for data_type, records in data.items():
            filename = f"{output_dir}/raw_{data_type}.json"
            with open(filename, "w") as f:
                json.dump(records, f, indent=2)
            print(f"✅ Saved {len(records):,} {data_type} to {filename}")

        # Save summary
        summary = {
            "generated_at": datetime.now().isoformat(),
            "shops": self.shops,
            "totals": {data_type: len(records) for data_type, records in data.items()},
            "total_records": sum(len(records) for records in data.values()),
        }

        with open(f"{output_dir}/summary.json", "w") as f:
            json.dump(summary, f, indent=2)
        print(f"✅ Saved summary to {output_dir}/summary.json")

    def print_data_summary(self, data: Dict[str, List[Dict[str, Any]]]):
        """Print a summary of generated data"""
        print("\n" + "=" * 60)
        print("📊 DATA GENERATION SUMMARY")
        print("=" * 60)

        for data_type, records in data.items():
            print(f"{data_type.upper():<20}: {len(records):>8,} records")

        total_records = sum(len(records) for records in data.values())
        print("-" * 60)
        print(f"{'TOTAL':<20}: {total_records:>8,} records")
        print("=" * 60)

        # Per-shop breakdown
        print("\n🏪 PER-SHOP BREAKDOWN:")
        for shop in self.shops:
            shop_id = shop["id"]
            shop_name = shop["name"]
            print(f"\n{shop_name} ({shop_id}):")

            for data_type, records in data.items():
                shop_records = [r for r in records if r["shopId"] == shop_id]
                print(f"  {data_type:<18}: {len(shop_records):>6,} records")

    def generate_and_save(
        self,
        volume: str = "medium",
        save_to_files: bool = True,
        output_dir: str = "generated_data",
    ):
        """Generate all data and optionally save to files"""
        # Generate data
        data = self.generate_all_data(volume)

        # Print summary
        self.print_data_summary(data)

        # Save to files if requested
        if save_to_files:
            self.save_data_to_files(data, output_dir)

        return data


def main():
    """Main function for command-line usage"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate comprehensive test data for BetterBundle pipeline"
    )
    parser.add_argument(
        "--volume",
        choices=["small", "medium", "large"],
        default="medium",
        help="Data volume to generate (default: medium)",
    )
    parser.add_argument(
        "--output-dir",
        default="generated_data",
        help="Output directory for generated files (default: generated_data)",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Don't save data to files, just generate in memory",
    )

    args = parser.parse_args()

    # Create generator and run
    generator = MainDataGenerator()
    data = generator.generate_and_save(
        volume=args.volume, save_to_files=not args.no_save, output_dir=args.output_dir
    )

    print(f"\n🎯 Data generation complete! Use this data to test your pipeline.")


if __name__ == "__main__":
    main()
