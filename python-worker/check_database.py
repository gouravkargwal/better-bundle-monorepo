#!/usr/bin/env python3
"""
Check database for stored data
"""

import asyncio
import os
from prisma import Prisma
from dotenv import load_dotenv

async def check_database():
    """Check what data was stored in the database"""
    
    # Load environment variables
    load_dotenv()
    
    database_url = os.getenv("DATABASE_URL")
    print(f"Database URL: {database_url}")
    
    try:
        # Initialize Prisma client
        db = Prisma()
        await db.connect()
        print("✅ Database connection successful")
        
        # Check shops
        shops = await db.shop.find_many()
        print(f"📊 Shops in DB: {len(shops)}")
        for shop in shops:
            print(f"   - Shop ID: {shop.id}, Domain: {shop.shopDomain}")
        
        # Check raw products
        products = await db.rawproduct.find_many()
        print(f"📦 Raw Products in DB: {len(products)}")
        
        # Check raw orders
        orders = await db.raworder.find_many()
        print(f"📋 Raw Orders in DB: {len(orders)}")
        
        # Check raw customers
        customers = await db.rawcustomer.find_many()
        print(f"👥 Raw Customers in DB: {len(customers)}")
        
        # Check raw collections
        collections = await db.rawcollection.find_many()
        print(f"🗂️ Raw Collections in DB: {len(collections)}")
        
        # Check raw customer events
        events = await db.rawcustomerevent.find_many()
        print(f"📈 Raw Customer Events in DB: {len(events)}")
        
        await db.disconnect()
        print("✅ Database connection closed")
        
    except Exception as e:
        print(f"❌ Database check failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_database())
