from decimal import Decimal

from fastapi import HTTPException, Depends, status, APIRouter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import Movie, UserModel, get_db
from database.models import (
    OrderModel,
    OrderItemModel,
    OrderStatusEnum,
    Cart,
    CartItem,
)
from routes.accounts import get_current_user
from schemas.orders import (
    OrderItemResponseSchema,
    OrderResponseSchema,
    OrderCreateSchema,
    OrderListResponseSchema,
    OrderMovieSchema,
)

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.post(
    "/",
    response_model=OrderResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new order from the user's cart",
)
async def create_order(
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    cart = await db.scalar(
        select(Cart)
        .options(selectinload(Cart.items).selectinload(CartItem.movie))
        .where(Cart.user_id == current_user.id)
    )

    if not cart or not cart.items:
        raise HTTPException(status_code=400, detail="Cart is empty.")

    available_items = cart.items

    purchased_stmt = (
        select(OrderItemModel.movie_id)
        .join(OrderModel)
        .where(
            OrderModel.user_id == current_user.id,
            OrderModel.status == OrderStatusEnum.PAID,
        )
    )
    purchased = set(await db.scalars(purchased_stmt))
    available_items = [
        i for i in available_items if i.movie.id not in purchased
    ]

    if not available_items:
        raise HTTPException(
            status_code=400, detail="All movies are already purchased."
        )

    pending_stmt = (
        select(OrderItemModel.movie_id)
        .join(OrderModel)
        .where(
            OrderModel.user_id == current_user.id,
            OrderModel.status == OrderStatusEnum.PENDING,
        )
    )
    pending = set(await db.scalars(pending_stmt))
    available_items = [i for i in available_items if i.movie.id not in pending]

    if not available_items:
        raise HTTPException(
            status_code=400,
            detail="All movies are already pending in another order.",
        )

    total = sum(Decimal(i.movie.price) for i in available_items)

    order = OrderModel(
        user_id=current_user.id,
        total_amount=total,
        status=OrderStatusEnum.PENDING,
    )
    db.add(order)
    await db.flush()

    for item in available_items:
        db.add(
            OrderItemModel(
                order_id=order.id,
                movie_id=item.movie.id,
                price_at_order=Decimal(item.movie.price),
            )
        )

    for item in cart.items:
        await db.delete(item)

    await db.commit()
    await db.refresh(order, ["order_items"])

    return OrderResponseSchema(
        id=order.id,
        total_amount=order.total_amount,
        status=order.status,
        created_at=order.created_at,
        movies=[
            OrderItemResponseSchema(
                movie_id=i.movie.id,
                title=i.movie.name,
                price_at_order=i.price_at_order,
            )
            for i in order.order_items
        ],
    )


@router.get("/", response_model=list[OrderListResponseSchema])
async def get_user_orders(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    orders = await db.scalars(
        select(OrderModel)
        .where(OrderModel.user_id == current_user.id)
        .options(
            selectinload(OrderModel.order_items).selectinload(
                OrderItemModel.movie
            )
        )
        .order_by(OrderModel.created_at.desc())
    )
    orders = orders.all()

    if not orders:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No orders found for this user.",
        )

    return [
        OrderListResponseSchema(
            id=o.id,
            total_amount=o.total_amount,
            status=o.status.value if hasattr(o.status, "value") else o.status,
            created_at=o.created_at,
            movies=[
                OrderMovieSchema(
                    movie_id=i.movie.id,
                    title=i.movie.name,
                    price_at_order=i.price_at_order,
                )
                for i in o.order_items
            ],
        )
        for o in orders
    ]


@router.patch("/{order_id}/cancel", response_model=OrderListResponseSchema)
async def cancel_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    order = await db.scalar(
        select(OrderModel)
        .where(
            OrderModel.id == order_id, OrderModel.user_id == current_user.id
        )
        .options(
            selectinload(OrderModel.order_items).selectinload(
                OrderItemModel.movie
            )
        )
    )

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Order not found."
        )

    if order.status != OrderStatusEnum.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending orders can be canceled.",
        )

    order.status = OrderStatusEnum.CANCELED
    await db.commit()
    await db.refresh(order)

    return OrderListResponseSchema(
        id=order.id,
        total_amount=order.total_amount,
        status=order.status.value,
        created_at=order.created_at,
        movies=[
            OrderMovieSchema(
                movie_id=i.movie.id,
                title=i.movie.name,
                price_at_order=i.price_at_order,
            )
            for i in order.order_items
        ],
    )
