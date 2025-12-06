#!/usr/bin/env python3
"""Test script to diagnose Gorse connection issues"""
import asyncio
import httpx
import socket


async def test_connection():
    """Test httpx connection to Gorse"""
    # Test DNS resolution
    try:
        ip = socket.gethostbyname("gorse")
        print(f"✓ DNS resolution works: gorse -> {ip}")
    except Exception as e:
        print(f"✗ DNS resolution failed: {e}")
        return

    # Test with IP address
    print("\nTesting with IP address...")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"http://{ip}:8088/api/health/ready")
            print(f"✓ IP connection works: {response.status_code}")
    except Exception as e:
        print(f"✗ IP connection failed: {type(e).__name__}: {e}")

    # Test with hostname
    print("\nTesting with hostname...")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("http://gorse:8088/api/health/ready")
            print(f"✓ Hostname connection works: {response.status_code}")
    except Exception as e:
        print(f"✗ Hostname connection failed: {type(e).__name__}: {e}")
        if hasattr(e, "args") and e.args:
            print(f"  Exception args: {e.args}")


if __name__ == "__main__":
    asyncio.run(test_connection())
