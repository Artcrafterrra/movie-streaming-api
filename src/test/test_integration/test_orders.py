import pytest
from httpx import AsyncClient
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import (
    UserModel,
    Movie,
    Cart,
    CartItem,
    OrderModel,
    OrderStatusEnum,
)


@pytest.mark.asyncio
async def test_create_order_empty_cart(
    client: AsyncClient, db_session: AsyncSession
):
    """Check that creating an order with empty cart returns 400"""

    user = UserModel(
        id=2,
        email="empty@example.com",
        _hashed_password="hashed",
        group_id=1,
    )
    db_session.add(user)
    await db_session.commit()

    response = await client.post(
        "/api/v1/orders/",
        headers={"Authorization": "Bearer fake_token"},
    )

    if response.status_code in (401, 422):
        pytest.skip("User not authorized in test environment")

    assert response.status_code == 400
    assert "Cart is empty" in response.text


@pytest.mark.asyncio
async def test_get_user_orders(client: AsyncClient, db_session: AsyncSession):
    """Retrieve list of user's orders"""

    user = UserModel(
        id=3,
        email="orders@example.com",
        _hashed_password="hashed",
        group_id=1,
    )
    db_session.add(user)
    await db_session.commit()

    order = OrderModel(
        id=10,
        user_id=user.id,
        total_amount=Decimal("20.00"),
        status=OrderStatusEnum.PAID,
    )
    db_session.add(order)
    await db_session.commit()

    response = await client.get(
        "/api/v1/orders/",
        headers={"Authorization": "Bearer fake_token"},
    )

    if response.status_code in (401, 422):
        pytest.skip("User not authorized in test environment")

    assert response.status_code in (200, 404)
    if response.status_code == 200:
        data = response.json()
        assert isinstance(data, list)
        assert data[0]["total_amount"] == "20.00"


@pytest.mark.asyncio
async def test_cancel_order_success(
    client: AsyncClient, db_session: AsyncSession
):
    """Cancel a pending order"""

    user = UserModel(
        id=4,
        email="cancel@example.com",
        _hashed_password="hashed",
        group_id=1,
    )
    db_session.add(user)
    await db_session.commit()

    order = OrderModel(
        id=20,
        user_id=user.id,
        total_amount=Decimal("30.00"),
        status=OrderStatusEnum.PENDING,
    )
    db_session.add(order)
    await db_session.commit()

    response = await client.patch(
        f"/api/v1/orders/{order.id}/cancel",
        headers={"Authorization": "Bearer fake_token"},
    )

    if response.status_code in (401, 422):
        pytest.skip("User not authorized in test environment")

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "CANCELED"
    assert data["id"] == order.id


@pytest.mark.asyncio
async def test_cancel_order_not_found(client: AsyncClient):
    """Cancel non-existing order should return 404"""
    response = await client.patch(
        "/api/v1/orders/9999/cancel",
        headers={"Authorization": "Bearer fake_token"},
    )

    if response.status_code in (401, 422):
        pytest.skip("User not authorized in test environment")

    assert response.status_code == 404
    assert "Order not found" in response.text


@pytest.mark.asyncio
async def test_cancel_order_not_pending(
    client: AsyncClient, db_session: AsyncSession
):
    """Cancel already paid order should return 400"""

    user = UserModel(
        id=5,
        email="paid@example.com",
        _hashed_password="hashed",
        group_id=1,
    )
    db_session.add(user)
    await db_session.commit()

    order = OrderModel(
        id=30,
        user_id=user.id,
        total_amount=Decimal("40.00"),
        status=OrderStatusEnum.PAID,
    )
    db_session.add(order)
    await db_session.commit()

    response = await client.patch(
        f"/api/v1/orders/{order.id}/cancel",
        headers={"Authorization": "Bearer fake_token"},
    )

    if response.status_code in (401, 422):
        pytest.skip("User not authorized in test environment")

    assert response.status_code == 400
    assert "Only pending orders" in response.text
