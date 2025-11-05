from app.services.jwt_service import jwt_service
from app.models.auth_models import GenerateTokenRequest, RefreshTokenRequest
from fastapi import HTTPException
from app.repository.CustomerRepository import CustomerRepository
from app.repository.ShopRepository import ShopRepository
from app.core.logging import get_logger
from fastapi import status
from sqlalchemy.exc import NoResultFound

logger = get_logger(__name__)


class AuthController:
    def __init__(self):
        self.jwt_service = jwt_service
        self.customer_repository = CustomerRepository()
        self.shop_repository = ShopRepository()

    async def generate_shop_token(self, request: GenerateTokenRequest):
        try:
            shop_domain = request.shop_domain
            if not shop_domain and request.customer_id:
                shop_domain = await self.customer_repository.get_shop_domain_from_id(
                    request.customer_id
                )
            if not shop_domain:
                raise HTTPException(status_code=400, detail="Shop domain is required")

            shop_info = await self.shop_repository.get_shop_info_from_domain(
                shop_domain
            )

            token_pair = self.jwt_service.create_token_pair(
                shop_id=shop_info["shop_id"],
                shop_domain=shop_info["shop_domain"],
                is_service_active=shop_info["is_service_active"],
                shopify_plus=shop_info["shopify_plus"],
            )

            # Add needs_refresh field (False for newly generated tokens)
            token_pair["needs_refresh"] = False

            return token_pair
        except NoResultFound:
            # ✅ Catch database exception and convert to HTTP exception
            raise HTTPException(
                status_code=404, detail=f"Shop not found for domain: {shop_domain}"
            )
        except HTTPException:
            raise  # Re-raise HTTP exceptions as-is
        except Exception as e:
            logger.error(f"Error generating shop token: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to generate shop token")

    async def refresh_access_token(self, request: RefreshTokenRequest):
        """
        Refresh access token using refresh token.

        Flow:
        1. Validate refresh token
        2. If expired → Query DB → Regenerate pair with fresh status
        3. If valid → Create new access token (no DB needed)
        """
        try:
            logger.info("Attempting to refresh access token")

            # Validate refresh token
            refresh_result = self.jwt_service.validate_refresh_token(
                request.refresh_token
            )

            # Handle refresh token expired - ONLY TIME WE NEED DB
            if (
                not refresh_result.get("is_valid")
                and refresh_result.get("error_code") == "REFRESH_TOKEN_EXPIRED"
            ):
                logger.info("Refresh token expired - regenerating from DB")

                shop_id = refresh_result.get("shop_id")

                if not shop_id:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Cannot extract shop info from expired token",
                    )

                # DB check only here
                shop_info = await self.shop_repository.get_shop_by_id(shop_id)

                # Regenerate with fresh DB data
                token_pair = self.jwt_service.create_token_pair(
                    shop_id=shop_info["shop_id"],
                    shop_domain=shop_info["shop_domain"],
                    is_service_active=shop_info["is_service_active"],
                    shopify_plus=shop_info.get("shopify_plus", False),
                )

                logger.info(
                    f"Token pair regenerated from DB for {shop_info['shop_domain']}"
                )

                return {
                    "refresh_expires_in": int(
                        self.jwt_service.refresh_token_expire.total_seconds()
                    ),
                    "refresh_token": token_pair["refresh_token"],
                    "access_token": token_pair["access_token"],
                    "expires_in": int(
                        self.jwt_service.access_token_expire.total_seconds()
                    ),
                }

            # Handle other validation errors
            if not refresh_result.get("is_valid"):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=refresh_result.get("error", "Invalid refresh token"),
                    headers={"WWW-Authenticate": "Bearer"},
                )

            # Refresh token is VALID - NO DB QUERY NEEDED
            # Use values stored in refresh token payload (from original token creation)
            logger.info(
                f"Generating new access token for {refresh_result['shop_domain']}"
            )

            access_token = self.jwt_service.create_access_token(
                shop_id=refresh_result["shop_id"],
                shop_domain=refresh_result["shop_domain"],
                is_service_active=refresh_result.get("is_service_active", True),
                shopify_plus=refresh_result.get("shopify_plus", False),
            )

            return {
                "access_token": access_token,
                "refresh_token": request.refresh_token,  # Return same refresh token
                "expires_in": int(self.jwt_service.access_token_expire.total_seconds()),
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Token refresh error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to refresh token",
            )


auth_controller = AuthController()
