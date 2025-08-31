from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
from datetime import datetime
import os
from prisma import Prisma

# Import from our modular cosine_similarity package
from cosine_similarity import (
    BundleAnalyzer,
    ProductData,
    OrderData,
    BundleAnalysisRequest,
    CosineSimilarityRequest,
    BundleAnalysisResponse,
    CosineSimilarityResponse,
    SimilarityConfig,
    BundleConfig,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="BetterBundle ML API",
    description="Machine Learning API for bundle analysis and cosine similarity calculations",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global storage for analysis results (in production, use Redis or database)
analysis_cache = {}

# Initialize analyzer with default configuration
analyzer = BundleAnalyzer()

# Initialize Prisma client with shared schema
prisma = Prisma()


# Connect to database on startup
@app.on_event("startup")
async def startup():
    await prisma.connect()


@app.on_event("shutdown")
async def shutdown():
    await prisma.disconnect()


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "BetterBundle ML API is running",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "cosine_similarity": "/api/cosine-similarity",
            "bundle_analysis": "/api/bundle-analysis",
            "docs": "/docs",
        },
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "BetterBundle ML API",
    }


@app.post("/api/cosine-similarity", response_model=CosineSimilarityResponse)
async def calculate_cosine_similarity(request: CosineSimilarityRequest):
    """Calculate cosine similarity between products"""
    try:
        logger.info(
            f"Calculating cosine similarity for {len(request.product_features)} products"
        )

        # Convert to ProductData objects
        products = [ProductData(**product) for product in request.product_features]

        # Calculate similarity
        similarity_results = analyzer.calculate_cosine_similarity(products)

        # Filter for target product if specified
        if request.target_product_id:
            target_similarities = next(
                (
                    sim
                    for sim in similarity_results["product_similarities"]
                    if sim["product_id"] == request.target_product_id
                ),
                None,
            )
            if target_similarities:
                similarities = target_similarities["similar_products"][: request.top_k]
            else:
                similarities = []
        else:
            # Return top similarities for all products
            similarities = []
            for product_sim in similarity_results["product_similarities"]:
                similarities.extend(product_sim["similar_products"][: request.top_k])

        return CosineSimilarityResponse(
            success=True,
            similarities=similarities,
            matrix=similarity_results["similarity_matrix"],
            metadata={
                "total_products": len(products),
                "analysis_timestamp": datetime.now().isoformat(),
                "target_product_id": request.target_product_id,
                "top_k": request.top_k,
            },
        )

    except Exception as e:
        logger.error(f"Error in cosine similarity endpoint: {str(e)}")
        return CosineSimilarityResponse(
            success=False, similarities=[], metadata={}, error=str(e)
        )


@app.post("/api/bundle-analysis", response_model=BundleAnalysisResponse)
async def analyze_bundles(request: BundleAnalysisRequest):
    """Analyze bundles using cosine similarity and co-purchase patterns"""
    try:
        logger.info(f"Starting bundle analysis for shop {request.shop_id}")
        logger.info(f"Products: {len(request.products)}, Orders: {len(request.orders)}")

        # Configure analyzer if custom config provided
        if request.analysis_config:
            similarity_config = SimilarityConfig(
                **request.analysis_config.get("similarity", {})
            )
            bundle_config = BundleConfig(**request.analysis_config.get("bundle", {}))
            custom_analyzer = BundleAnalyzer(similarity_config, bundle_config)
        else:
            custom_analyzer = analyzer

        # Perform analysis
        analysis_results = custom_analyzer.analyze_bundles(
            request.products, request.orders
        )

        # Cache results
        analysis_cache[request.shop_id] = {
            "results": analysis_results,
            "timestamp": datetime.now().isoformat(),
        }

        return BundleAnalysisResponse(
            success=True,
            bundles=analysis_results["bundles"],
            similarity_matrix=analysis_results["similarity_matrix"],
            metadata=analysis_results["metadata"],
        )

    except Exception as e:
        logger.error(f"Error in bundle analysis endpoint: {str(e)}")
        return BundleAnalysisResponse(
            success=False, bundles=[], metadata={}, error=str(e)
        )


@app.post("/api/bundle-analysis/{shop_id}")
async def analyze_bundles_from_db(shop_id: str):
    """Analyze bundles using data from database"""
    try:
        logger.info(f"Starting bundle analysis for shop {shop_id} from database")

        # Get shop data
        shop = await prisma.shop.find_unique(
            where={"shopId": shop_id}, select={"id": True}
        )

        if not shop:
            raise HTTPException(status_code=404, detail="Shop not found")

        # Get products from database
        products_db = await prisma.productdata.find_many(
            where={"shopId": shop["id"], "isActive": True}
        )

        # Get orders from database
        orders_db = await prisma.orderdata.find_many(where={"shopId": shop["id"]})

        logger.info(
            f"Found {len(products_db)} products and {len(orders_db)} orders in database"
        )

        # Convert to ProductData objects
        products = []
        for product in products_db:
            products.append(
                ProductData(
                    product_id=product.productId,
                    title=product.title,
                    category=product.category,
                    price=product.price,
                    tags=product.tags if product.tags else [],
                    description="",  # Not stored in DB
                    image_url=product.imageUrl,
                )
            )

        # Convert to OrderData objects
        orders = []
        for order in orders_db:
            orders.append(
                OrderData(
                    order_id=order.orderId,
                    customer_id=order.customerId,
                    total_amount=order.totalAmount,
                    order_date=order.orderDate.isoformat(),
                    line_items=order.lineItems,
                )
            )

        # Perform analysis
        analysis_results = analyzer.analyze_bundles(products, orders)

        # Save results to database
        if analysis_results["bundles"]:
            # Clear existing results
            await prisma.bundleanalysisresult.delete_many(where={"shopId": shop["id"]})

            # Save new results
            bundle_data = []
            for bundle in analysis_results["bundles"]:
                bundle_data.append(
                    {
                        "shopId": shop["id"],
                        "productIds": bundle["product_ids"],
                        "bundleSize": len(bundle["product_ids"]),
                        "coPurchaseCount": bundle["co_purchase_count"],
                        "confidence": bundle["confidence"],
                        "lift": bundle["lift"],
                        "support": bundle["support"],
                        "revenue": bundle.get("revenue_potential", 0),
                        "avgOrderValue": bundle.get("total_price", 0),
                        "discount": 0,
                        "isActive": True,
                    }
                )

            await prisma.bundleanalysisresult.create_many(data=bundle_data)

        return BundleAnalysisResponse(
            success=True,
            bundles=analysis_results["bundles"],
            similarity_matrix=analysis_results["similarity_matrix"],
            metadata=analysis_results["metadata"],
        )

    except Exception as e:
        logger.error(f"Error in bundle analysis from database: {str(e)}")
        return BundleAnalysisResponse(
            success=False, bundles=[], metadata={}, error=str(e)
        )


@app.get("/api/bundle-analysis/{shop_id}")
async def get_cached_analysis(shop_id: str):
    """Get cached bundle analysis results"""
    try:
        if shop_id in analysis_cache:
            return {"success": True, "data": analysis_cache[shop_id]}
        else:
            raise HTTPException(
                status_code=404, detail="Analysis not found for this shop"
            )
    except Exception as e:
        logger.error(f"Error retrieving cached analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/bundle-analysis/{shop_id}")
async def clear_cached_analysis(shop_id: str):
    """Clear cached analysis results"""
    try:
        if shop_id in analysis_cache:
            del analysis_cache[shop_id]
            return {"success": True, "message": "Cache cleared"}
        else:
            return {"success": True, "message": "No cache found"}
    except Exception as e:
        logger.error(f"Error clearing cache: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/similar-products/{product_id}")
async def get_similar_products(product_id: str, request: CosineSimilarityRequest):
    """Get similar products for a specific product"""
    try:
        logger.info(f"Getting similar products for {product_id}")

        # Convert to ProductData objects
        products = [ProductData(**product) for product in request.product_features]

        # Get similar products
        similar_products = analyzer.get_similar_products(
            product_id, products, request.top_k
        )

        return {
            "success": True,
            "product_id": product_id,
            "similar_products": similar_products,
            "metadata": {
                "total_products": len(products),
                "analysis_timestamp": datetime.now().isoformat(),
                "top_k": request.top_k,
            },
        }

    except Exception as e:
        logger.error(f"Error getting similar products: {str(e)}")
        return {
            "success": False,
            "product_id": product_id,
            "similar_products": [],
            "error": str(e),
        }


@app.get("/api/config")
async def get_config():
    """Get current configuration"""
    return {
        "success": True,
        "config": {
            "similarity": analyzer.similarity_config.dict(),
            "bundle": analyzer.bundle_config.dict(),
        },
    }


@app.post("/api/config")
async def update_config(request: dict):
    """Update configuration"""
    try:
        global analyzer

        # Update similarity config
        if "similarity" in request:
            similarity_config = SimilarityConfig(**request["similarity"])
        else:
            similarity_config = analyzer.similarity_config

        # Update bundle config
        if "bundle" in request:
            bundle_config = BundleConfig(**request["bundle"])
        else:
            bundle_config = analyzer.bundle_config

        # Create new analyzer with updated config
        analyzer = BundleAnalyzer(similarity_config, bundle_config)

        return {
            "success": True,
            "message": "Configuration updated successfully",
            "config": {
                "similarity": analyzer.similarity_config.dict(),
                "bundle": analyzer.bundle_config.dict(),
            },
        }

    except Exception as e:
        logger.error(f"Error updating configuration: {str(e)}")
        return {
            "success": False,
            "error": str(e),
        }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
