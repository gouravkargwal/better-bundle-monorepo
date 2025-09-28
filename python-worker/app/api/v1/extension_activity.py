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
from app.core.database.session import get_transaction_context
from app.core.database.models.extension import (
    ExtensionActivity as ExtensionActivityModel,
)
from app.core.database.models.shop import Shop
from sqlalchemy import select, and_, or_, desc, func, update
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
        async with get_transaction_context() as session:
            # Determine shop_id based on what's provided
            shop_id = None

            if request.shop_domain:
                # Use shop domain to get shop_id
                shop_id = await shop_resolver.get_shop_id_from_domain(
                    request.shop_domain
                )
                logger.info(
                    f"Resolved shop_id from domain: {request.shop_domain} -> {shop_id}"
                )
            elif request.customer_id:
                # Use customer_id to get shop_id
                logger.info(
                    f"Attempting to resolve shop_id from customer_id: {request.customer_id}"
                )
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
                    status_code=404,
                    detail="Shop not found with the provided identifier",
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
            existing_stmt = select(ExtensionActivityModel).where(
                and_(
                    ExtensionActivityModel.shop_id == shop_id,
                    ExtensionActivityModel.extension_type == request.extension_type,
                    ExtensionActivityModel.extension_uid == request.extension_uid,
                    ExtensionActivityModel.last_seen > cutoff_time,
                )
            )
            existing_result = await session.execute(existing_stmt)
            existing = existing_result.scalar_one_or_none()

            if existing:
                # Just update last_seen
                now = now_utc()
                update_stmt = (
                    update(ExtensionActivityModel)
                    .where(ExtensionActivityModel.id == existing.id)
                    .values(
                        last_seen=now,
                        updated_at=now,
                    )
                )
                await session.execute(update_stmt)
                await session.commit()
                result = existing
            else:
                # Create new or update existing
                now = now_utc()

                # Check if record exists (for upsert)
                upsert_stmt = select(ExtensionActivityModel).where(
                    and_(
                        ExtensionActivityModel.shop_id == shop_id,
                        ExtensionActivityModel.extension_type == request.extension_type,
                        ExtensionActivityModel.extension_uid == request.extension_uid,
                    )
                )
                upsert_result = await session.execute(upsert_stmt)
                existing_record = upsert_result.scalar_one_or_none()

                if existing_record:
                    # Update existing record
                    update_stmt = (
                        update(ExtensionActivityModel)
                        .where(ExtensionActivityModel.id == existing_record.id)
                        .values(
                            extension_name=extension_name,
                            app_block_target=request.app_block_target,
                            page_url=request.page_url,
                            app_block_location=request.app_block_location,
                            last_seen=now,
                            is_active=True,
                            updated_at=now,
                        )
                    )
                    await session.execute(update_stmt)
                    await session.commit()
                    result = existing_record
                else:
                    # Create new record
                    new_activity = ExtensionActivityModel(
                        shop_id=shop_id,
                        extension_type=request.extension_type,
                        extension_uid=request.extension_uid,
                        extension_name=extension_name,
                        app_block_target=request.app_block_target,
                        page_url=request.page_url,
                        app_block_location=request.app_block_location,
                        last_seen=now,
                        is_active=True,
                        created_at=now,
                        updated_at=now,
                    )
                    session.add(new_activity)
                    await session.commit()
                    await session.refresh(new_activity)
                    result = new_activity

            if not result:
                raise HTTPException(
                    status_code=500, detail="Failed to track extension activity"
                )

            logger.info(
                f"Successfully tracked extension activity for shop_id: {shop_id}, extension: {request.extension_type}"
            )

            return ExtensionActivityResponse(
                id=result.id,
                shop_id=result.shop_id,
                extension_type=result.extension_type,
                extension_uid=result.extension_uid,
                extension_name=result.extension_name,
                app_block_target=result.app_block_target,
                page_url=result.page_url,
                app_block_location=result.app_block_location,
                last_seen=result.last_seen.isoformat(),
                is_active=result.is_active,
                created_at=result.created_at.isoformat(),
                updated_at=result.updated_at.isoformat(),
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to track extension load (unified): {e}")
        raise HTTPException(status_code=500, detail=str(e))
