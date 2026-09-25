from sqladmin import BaseView, expose
from starlette.requests import Request
from app.core.database.session import get_transaction_context
from app.core.config.settings import settings
from sqlalchemy import text


_BUSINESS_HEALTH_SQL = text(
    """
    SELECT
      s.id,
      s.shop_domain,
      s.is_active,
      COALESCE(i.impressions_24h, 0)      AS impressions_24h,
      COALESCE(i.clicks_24h, 0)           AS clicks_24h,
      COALESCE(a.attributed_orders_7d, 0) AS attributed_orders_7d,
      COALESCE(a.revenue_7d, 0)           AS revenue_7d,
      i.last_impression_at,
      CASE
        WHEN s.is_active = false THEN 'inactive'
        WHEN i.last_impression_at IS NULL THEN 'never_served'
        WHEN i.last_impression_at < now() - interval '6 hours'
             THEN 'silent'
        WHEN COALESCE(i.impressions_24h, 0) > 0
             AND COALESCE(i.clicks_24h, 0) = 0
             THEN 'no_engagement'
        ELSE 'healthy'
      END AS status
    FROM shops s
    LEFT JOIN (
      SELECT shop_id,
             COUNT(*) FILTER (
               WHERE created_at > now() - interval '24 hours'
             ) AS impressions_24h,
             COUNT(*) FILTER (
               WHERE created_at > now() - interval '24 hours'
                 AND outcome = 'clicked'
                 AND is_control = false
             ) AS clicks_24h,
             MAX(created_at) AS last_impression_at
      FROM offer_impressions
      WHERE is_control = false
      GROUP BY shop_id
    ) i ON i.shop_id = s.id
    LEFT JOIN (
      SELECT pa.shop_id,
             COUNT(DISTINCT pa.order_id) AS attributed_orders_7d,
             COALESCE(SUM(cr.commission_charged), 0) AS revenue_7d
      FROM purchase_attributions pa
      LEFT JOIN commission_records cr
        ON cr.purchase_attribution_id = pa.id
      WHERE pa.purchase_at > now() - interval '7 days'
      GROUP BY pa.shop_id
    ) a ON a.shop_id = s.id
    ORDER BY
      CASE
        WHEN s.is_active = false THEN 4
        WHEN i.last_impression_at IS NULL THEN 1
        WHEN i.last_impression_at < now() - interval '6 hours' THEN 1
        WHEN COALESCE(i.impressions_24h, 0) > 0
             AND COALESCE(i.clicks_24h, 0) = 0 THEN 2
        ELSE 3
      END,
      a.revenue_7d DESC NULLS LAST
    """
)


class BusinessHealthView(BaseView):
    name = "Business Health"
    icon = "fa-solid fa-heart-pulse"

    @expose("/business-health", methods=["GET"])
    async def business_health(self, request: Request) -> str:
        async with get_transaction_context() as session:
            rows = (await session.execute(_BUSINESS_HEALTH_SQL)).all()

        statuses = {"healthy", "silent", "never_served", "no_engagement", "inactive"}
        cleaned = []
        for row in rows:
            data = dict(row._mapping)
            if data.get("status") not in statuses:
                data["status"] = "unknown"
            cleaned.append(data)

        return await self.templates.TemplateResponse(
            request,
            "business_health.html",
            {
                "rows": cleaned,
                "title": "Business Health",
            },
        )
