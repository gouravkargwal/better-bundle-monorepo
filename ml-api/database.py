from prisma import Prisma
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from local.env
env_path = Path(__file__).parent.parent.parent / "local.env"
load_dotenv(env_path)

# Initialize Prisma client
prisma = Prisma()


async def connect():
    """Connect to the database"""
    await prisma.connect()


async def disconnect():
    """Disconnect from the database"""
    await prisma.disconnect()


# Export the client for use in other modules
__all__ = ["prisma", "connect", "disconnect"]
