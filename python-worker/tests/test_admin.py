import pytest
from unittest.mock import MagicMock, patch
from unittest.mock import AsyncMock

from app.admin.auth import AdminAuth
from app.admin.views.shops import ShopAdmin
from app.core.database.models import Shop, BillingInvoice


@pytest.mark.asyncio
async def test_admin_auth_login_success():
    auth = AdminAuth(secret_key="test-secret")
    request = MagicMock()
    request.form = AsyncMock(return_value={"username": "admin", "password": "correct"})
    request.session = {}

    with patch("app.admin.auth.settings") as mock_settings:
        mock_settings.ADMIN_USERNAME = "admin"
        mock_settings.ADMIN_PASSWORD = "correct"
        result = await auth.login(request)

    assert result is True
    assert request.session.get("admin_user") == "admin"


@pytest.mark.asyncio
async def test_admin_auth_login_failure():
    auth = AdminAuth(secret_key="test-secret")
    request = MagicMock()
    request.form = AsyncMock(return_value={"username": "admin", "password": "wrong"})
    request.session = {}

    with patch("app.admin.auth.settings") as mock_settings:
        mock_settings.ADMIN_USERNAME = "admin"
        mock_settings.ADMIN_PASSWORD = "correct"
        result = await auth.login(request)

    assert result is False
    assert "admin_user" not in request.session


@pytest.mark.asyncio
async def test_admin_auth_timing_safe():
    auth = AdminAuth(secret_key="test-secret")
    request = MagicMock()
    request.form = AsyncMock(return_value={"username": "admin", "password": "correct"})
    request.session = {}

    with patch("app.admin.auth.settings") as mock_settings, \
         patch("app.admin.auth.secrets.compare_digest") as mock_digest:
        mock_settings.ADMIN_USERNAME = "admin"
        mock_settings.ADMIN_PASSWORD = "correct"
        mock_digest.return_value = True
        await auth.login(request)

    assert mock_digest.call_count == 2


@pytest.mark.asyncio
async def test_business_health_query_runs():
    from app.admin.custom.business_health import _BUSINESS_HEALTH_SQL

    from app.core.database.session import get_transaction_context

    async with get_transaction_context() as session:
        rows = (await session.execute(_BUSINESS_HEALTH_SQL)).all()

    statuses = {"healthy", "silent", "never_served", "no_engagement", "inactive"}
    for row in rows:
        data = dict(row._mapping)
        assert data.get("status") in statuses


def test_shop_admin_columns_resolve():
    admin = ShopAdmin()
    for col in admin.column_list:
        assert hasattr(Shop, col.name), f"Column {col.name} not found on Shop"


def test_billing_invoice_is_importable():
    assert hasattr(BillingInvoice, "__tablename__")
    assert BillingInvoice.__tablename__ == "billing_invoices"
