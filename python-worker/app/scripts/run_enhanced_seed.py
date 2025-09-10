#!/usr/bin/env python3
"""
Enhanced seed data runner - creates realistic user journeys for meaningful Gorse training.
"""
import asyncio
import sys
import os

# Add the python-worker directory to Python path
python_worker_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, python_worker_dir)

from seed_pipeline_runner import SeedPipelineRunner


async def main():
    """Run the enhanced seed data pipeline."""
    print("🎯 Enhanced Seed Data Pipeline")
    print("=" * 50)
    print("This will create realistic user journeys with:")
    print("• 15 diverse products across 3 categories")
    print("• 8 customer profiles with different behaviors")
    print("• 12 orders showing realistic purchase patterns")
    print("• 100+ behavioral events covering complete user journeys")
    print("• Cross-category recommendations and frequently bought together patterns")
    print("• Abandoned cart scenarios and new customer cold-start data")
    print("• VIP customer loyalty patterns and bargain hunter behaviors")
    print("=" * 50)

    runner = SeedPipelineRunner()
    success = await runner.run_complete_pipeline()

    if success:
        print("\n🎉 Enhanced seed data pipeline completed successfully!")
        print("🚀 Gorse now has rich, realistic data for meaningful recommendations!")
    else:
        print("\n❌ Enhanced seed data pipeline failed. Check logs above.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
