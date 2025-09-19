"""
Extension Activity API

Simple API to track when extensions load on pages.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Path, Body
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.core.database.simple_db_client import get_database
from app.shared.helpers import now_utc
from app.domains.analytics.services.shop_resolver import shop_resolver


# Request/Response Models
class ExtensionActivityRequest(BaseModel):
    """Request model for tracking extension activity"""

    extension_type: str = Field(
        ..., description="Extension type (apollo, atlas, phoenix, venus)"
    )
    extension_uid: str = Field(..., min_length=1, max_length=255)
    page_url: str = Field(..., max_length=500)
    app_block_target: Optional[str] = Field(
        None, description="App block target for Venus"
    )
    app_block_location: Optional[str] = Field(None, max_length=100)


class UnifiedExtensionActivityRequest(BaseModel):
    """Unified request model that can handle both shop domain and customer ID"""

    extension_type: str = Field(
        ..., description="Extension type (apollo, atlas, phoenix, venus)"
    )
    extension_uid: str = Field(..., min_length=1, max_length=255)
    page_url: str = Field(..., max_length=500)
    app_block_target: Optional[str] = Field(
        None, description="App block target for Venus"
    )
    app_block_location: Optional[str] = Field(None, max_length=100)
    shop_domain: Optional[str] = Field(
        None, description="Shop domain (e.g., 'mystore.myshopify.com')"
    )
    customer_id: Optional[str] = Field(
        None, description="Customer ID for shop identification"
    )


class ExtensionActivityResponse(BaseModel):
    """Response model for extension activity"""

    id: str
    shop_id: str
    extension_type: str
    extension_uid: str
    extension_name: str
    app_block_target: Optional[str] = None
    page_url: Optional[str] = None
    app_block_location: Optional[str] = None
    last_seen: str
    is_active: bool
    created_at: str
    updated_at: str


class ActiveExtensionsResponse(BaseModel):
    """Response model for active extensions"""

    shop_id: str
    extensions: Dict[str, Dict[str, Any]]


# Router setup
router = APIRouter(prefix="/extension-activity", tags=["extension-activity"])
logger = get_logger(__name__)


@router.post("/track-load", response_model=ExtensionActivityResponse)
async def track_extension_load_unified(
    request: UnifiedExtensionActivityRequest = Body(...),
):
    """Track when an extension loads on a page - unified endpoint that handles both shop domain and customer ID"""
    try:
        db = await get_database()

        # Determine shop_id based on what's provided
        shop_id = None

        if request.shop_domain:
            # Use shop domain to get shop_id
            shop_id = await shop_resolver.get_shop_id_from_domain(request.shop_domain)
            logger.info(
                f"Resolved shop_id from domain: {request.shop_domain} -> {shop_id}"
            )
        elif request.customer_id:
            # Use customer_id to get shop_id
            shop_id = await shop_resolver.get_shop_id_from_customer_id(
                request.customer_id
            )
            logger.info(
                f"Resolved shop_id from customer_id: {request.customer_id} -> {shop_id}"
            )
        else:
            raise HTTPException(
                status_code=400,
                detail="Either shop_domain or customer_id must be provided",
            )

        if not shop_id:
            raise HTTPException(
                status_code=404, detail="Shop not found with the provided identifier"
            )

        # Get extension name from type
        extension_names = {
            "apollo": "Apollo Post-Purchase",
            "atlas": "Atlas Web Pixel",
            "phoenix": "Phoenix Theme Extension",
            "venus": "Venus Customer Account",
        }

        extension_name = extension_names.get(
            request.extension_type, request.extension_type.title()
        )

        # Check if already tracked recently (within 1 hour)
        cutoff_time = now_utc() - timedelta(hours=1)
        existing = await db.extensionactivity.find_first(
            where={
                "shopId": shop_id,
                "extensionType": request.extension_type,
                "extensionUid": request.extension_uid,
                "lastSeen": {"gt": cutoff_time},
            }
        )

        if existing:
            # Just update last_seen
            now = now_utc()
            result = await db.extensionactivity.update(
                where={"id": existing.id},
                data={
                    "lastSeen": now,
                    "updatedAt": now,
                },
            )
        else:
            # Create new or update existing
            now = now_utc()
            # Prepare the data for both create and update
            create_data = {
                "shopId": shop_id,
                "extensionType": request.extension_type,
                "extensionUid": request.extension_uid,
                "extensionName": extension_name,
                "appBlockTarget": request.app_block_target,
                "pageUrl": request.page_url,
                "appBlockLocation": request.app_block_location,
                "lastSeen": now,
                "isActive": True,
            }

            update_data = {
                "extensionName": extension_name,
                "appBlockTarget": request.app_block_target,
                "pageUrl": request.page_url,
                "appBlockLocation": request.app_block_location,
                "lastSeen": now,
                "isActive": True,
                "updatedAt": now,
            }

            result = await db.extensionactivity.upsert(
                where={
                    "shopId_extensionType_extensionUid": {
                        "shopId": shop_id,
                        "extensionType": request.extension_type,
                        "extensionUid": request.extension_uid,
                    }
                },
                data={
                    "create": create_data,
                    "update": update_data,
                },
            )

        if not result:
            raise HTTPException(
                status_code=500, detail="Failed to track extension activity"
            )

        logger.info(
            f"Successfully tracked extension activity for shop_id: {shop_id}, extension: {request.extension_type}"
        )

        return ExtensionActivityResponse(
            id=result.id,
            shop_id=result.shopId,
            extension_type=result.extensionType,
            extension_uid=result.extensionUid,
            extension_name=result.extensionName,
            app_block_target=result.appBlockTarget,
            page_url=result.pageUrl,
            app_block_location=result.appBlockLocation,
            last_seen=result.lastSeen.isoformat(),
            is_active=result.isActive,
            created_at=result.createdAt.isoformat(),
            updated_at=result.updatedAt.isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to track extension load (unified): {e}")
        raise HTTPException(status_code=500, detail=str(e))
