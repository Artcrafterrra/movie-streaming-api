import uuid
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from database.models.base import Base
from database.models.accounts import UserGroupModel, UserGroupEnum, UserModel
from database.models.movies import Movie, CertificationEnum
from database.models.orders import OrderModel, OrderItemModel, OrderStatusEnum
from database.models.payments import PaymentStatusEnum
from payments.service import PaymentService


# -----------------------
# Database fixtures
# -----------------------
@pytest_asyncio.fixture()
async def engine():
    """Create async in-memory SQLite engine."""
    eng = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    try:
        yield eng
    finally:
        async with eng.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await eng.dispose()


@pytest_asyncio.fixture()
async def session(engine):
    """Create async session."""
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as s:
        yield s
        await s.rollback()


# -----------------------
# Factory fixtures
# -----------------------
@pytest_asyncio.fixture()
def user_factory(session):
    async def _create_user(email: str = None) -> UserModel:
        group = UserGroupModel(name=UserGroupEnum.USER)
        user = UserModel(
            email=email or f"user_{uuid.uuid4().hex[:8]}@example.com",
            _hashed_password="hash",
            is_active=True,
            group=group,
        )
        session.add_all([group, user])
        await session.flush()
        return user

    return _create_user


@pytest_asyncio.fixture()
def movie_factory(session):
    async def _create_movie(
        name: str | None = None,
        price: Decimal = Decimal("10.00"),
    ) -> Movie:
        m = Movie(
            name=name or f"Test Movie {uuid.uuid4().hex[:8]}",
            year=2020,
            time=120,
            imdb=7.5,
            votes=1000,
            description="desc",
            price=price,
            certification=CertificationEnum.PG,
        )
        session.add(m)
        await session.flush()
        return m

    return _create_movie


@pytest_asyncio.fixture()
def order_with_items_factory(session, movie_factory):
    async def _create_order(user: UserModel, items_count: int = 2) -> OrderModel:
        movies = [await movie_factory() for _ in range(items_count)]
        total_amount = sum(
            (Decimal(str(m.price)) for m in movies), Decimal("0.00")
        )
        order = OrderModel(
            user_id=user.id,
            status=OrderStatusEnum.PENDING,
            total_amount=total_amount,
        )
        session.add(order)
        await session.flush()

        for mv in movies:
            session.add(
                OrderItemModel(
                    order_id=order.id,
                    movie_id=mv.id,
                    price_at_order=Decimal(str(mv.price)),
                )
            )
        await session.flush()
        return order

    return _create_order


# -----------------------
# Tests
# -----------------------
@pytest.mark.asyncio
async def test_create_payment_full_amount_marks_order_paid(
    session, user_factory, order_with_items_factory
):
    svc = PaymentService()
    user = await user_factory()
    order = await order_with_items_factory(user, items_count=2)

    payment = await svc.create_payment(
        session,
        user_id=user.id,
        order_id=order.id,
        amount=Decimal(str(order.total_amount)),
        status=PaymentStatusEnum.SUCCESSFUL,
        external_payment_id=f"ext-{uuid.uuid4().hex}",
    )

    assert payment.id is not None
    await session.refresh(order)
    assert order.status == OrderStatusEnum.PAID


@pytest.mark.asyncio
async def test_create_payment_partial_amount_keeps_pending(
    session, user_factory, order_with_items_factory
):
    svc = PaymentService()
    user = await user_factory()
    order = await order_with_items_factory(user, items_count=2)

    half = Decimal(str(order.total_amount)) / 2
    await svc.create_payment(
        session,
        user_id=user.id,
        order_id=order.id,
        amount=half,
        status=PaymentStatusEnum.SUCCESSFUL,
        external_payment_id=f"ext-{uuid.uuid4().hex}",
    )

    await session.refresh(order)
    assert order.status == OrderStatusEnum.PENDING


@pytest.mark.asyncio
async def test_refund_payment_reverts_paid_if_no_other_payments(
    session, user_factory, order_with_items_factory
):
    svc = PaymentService()
    user = await user_factory()
    order = await order_with_items_factory(user, items_count=1)

    p = await svc.create_payment(
        session,
        user_id=user.id,
        order_id=order.id,
        amount=Decimal(str(order.total_amount)),
        status=PaymentStatusEnum.SUCCESSFUL,
        external_payment_id=f"ext-{uuid.uuid4().hex}",
    )
    await session.refresh(order)
    assert order.status == OrderStatusEnum.PAID

    await svc.refund_payment(session, payment_id=p.id)
    await session.refresh(order)
    assert order.status == OrderStatusEnum.PENDING


@pytest.mark.asyncio
async def test_cancel_payment_does_not_affect_refunded(
    session, user_factory, order_with_items_factory
):
    svc = PaymentService()
    user = await user_factory()
    order = await order_with_items_factory(user, items_count=1)

    p = await svc.create_payment(
        session,
        user_id=user.id,
        order_id=order.id,
        amount=Decimal(str(order.total_amount)),
        status=PaymentStatusEnum.SUCCESSFUL,
        external_payment_id=f"ext-{uuid.uuid4().hex}",
    )
    await svc.refund_payment(session, payment_id=p.id)
    p2 = await svc.cancel_payment(session, payment_id=p.id)
    assert p2.status == PaymentStatusEnum.REFUNDED


@pytest.mark.asyncio
async def test_compute_order_remaining_to_pay(
    session, user_factory, order_with_items_factory
):
    svc = PaymentService()
    user = await user_factory()
    order = await order_with_items_factory(user, items_count=2)
    total = Decimal(str(order.total_amount))

    await svc.create_payment(
        session,
        user_id=user.id,
        order_id=order.id,
        amount=total / 4,
        status=PaymentStatusEnum.SUCCESSFUL,
        external_payment_id=f"ext-{uuid.uuid4().hex}",
    )

    remaining = await svc.compute_order_remaining_to_pay(
        session, order_id=order.id
    )
    assert remaining == total * Decimal("0.75")
