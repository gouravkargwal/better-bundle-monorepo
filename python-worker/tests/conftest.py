import os


import pytest

SHOP_ID = "shop_42"
SHOP_DOMAIN = "test.myshopify.com"
USER_ID = "cust_123"
PRODUCT_IDS = ["prod_001", "prod_002", "prod_003"]

@pytest.fixture
def sample_gorse_items():
    return [
        {"Id": f"shop_{SHOP_ID}_{pid}", "Score": 0.9 - i * 0.1}
        for i, pid in enumerate(PRODUCT_IDS)
    ]
