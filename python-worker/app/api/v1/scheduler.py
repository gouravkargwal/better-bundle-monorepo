"""
Scheduler API endpoints for GitHub Actions cron integration
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Dict, Any

from app.services.scheduler_service import scheduler_service

router = APIRouter()


@router.post("/check-scheduled-analyses")
async def check_scheduled_analyses(background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """
    Check for shops due for analysis and trigger them
    This endpoint is called by GitHub Actions cron jobs
    """
    try:
        # Initialize scheduler service
        await scheduler_service.initialize()
        
        # Check and trigger scheduled analyses
        result = await scheduler_service.check_and_trigger_scheduled_analyses()
        
        if result["success"]:
            return {
                "success": True,
                "message": result["message"],
                "data": {
                    "shops_processed": result["shops_processed"],
                    "shops_failed": result["shops_failed"],
                    "results": result.get("results", []),
                    "timestamp": result["timestamp"]
                }
            }
        else:
            raise HTTPException(status_code=500, detail=result["error"])
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scheduler error: {str(e)}")


@router.get("/status")
async def get_scheduler_status() -> Dict[str, Any]:
    """Get scheduler status and statistics"""
    try:
        # Initialize scheduler service
        await scheduler_service.initialize()
        
        # Get scheduler status
        result = await scheduler_service.get_scheduler_status()
        
        if result["success"]:
            return {
                "success": True,
                "data": result
            }
        else:
            raise HTTPException(status_code=500, detail=result["error"])
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scheduler status error: {str(e)}")


@router.post("/trigger-manual/{shop_id}")
async def trigger_manual_analysis(shop_id: str) -> Dict[str, Any]:
    """Trigger manual analysis for a specific shop"""
    try:
        # Initialize scheduler service
        await scheduler_service.initialize()
        
        # Trigger manual analysis
        result = await scheduler_service.trigger_manual_analysis(shop_id)
        
        if result["success"]:
            return {
                "success": True,
                "message": "Manual analysis triggered successfully",
                "data": {
                    "job_id": result["job_id"],
                    "message_id": result["message_id"],
                    "shop_domain": result["shop_domain"],
                    "status": result["status"]
                }
            }
        else:
            raise HTTPException(status_code=400, detail=result["error"])
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Manual analysis error: {str(e)}")


@router.post("/update-schedule/{shop_id}")
async def update_analysis_schedule(shop_id: str, analysis_result: Dict[str, Any] = None) -> Dict[str, Any]:
    """Update analysis schedule for a shop after analysis completion"""
    try:
        # Initialize scheduler service
        await scheduler_service.initialize()
        
        # Update analysis schedule
        result = await scheduler_service.update_analysis_schedule(shop_id, analysis_result)
        
        if result["success"]:
            return {
                "success": True,
                "message": "Analysis schedule updated successfully",
                "data": {
                    "next_scheduled_time": result["next_scheduled_time"].isoformat() if result.get("next_scheduled_time") else None,
                    "heuristic_result": result.get("heuristic_result")
                }
            }
        else:
            raise HTTPException(status_code=400, detail=result["error"])
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Schedule update error: {str(e)}")


@router.get("/health")
async def scheduler_health() -> Dict[str, Any]:
    """Health check for scheduler service"""
    try:
        # Initialize scheduler service
        await scheduler_service.initialize()
        
        # Get basic status
        status = await scheduler_service.get_scheduler_status()
        
        return {
            "success": True,
            "status": "healthy",
            "message": "Scheduler service is running",
            "data": {
                "shops_due_for_analysis": status.get("shops_due_for_analysis", 0),
                "total_shops_with_auto_analysis": status.get("total_shops_with_auto_analysis", 0),
                "last_check": status.get("last_check")
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "status": "unhealthy",
            "error": str(e)
        }
