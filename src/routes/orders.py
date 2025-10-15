from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from sqlalchemy.orm import joinedload

from database import get_db
from database.models import (
    OrderModel,
    OrderItemModel,
    Movie,
    UserModel,
    Cart,
    CartItem,
)
from database.models.orders import OrderStatusEnum
from schemas.orders import (
    OrderCreateSchema,
    OrderResponseSchema,
    OrderUpdateSchema,
    OrderListResponseSchema,
    OrderCancelRequestSchema,
    OrderConfirmPaymentSchema,
    OrderListItemSchema,
    OrderItemDetailSchema,
    OrderDetailResponseSchema,
    OrderCancelResponseSchema,
)
from routes.accounts import get_current_user

router = APIRouter(prefix="/orders", tags=["Orders"])


async def _validate_movies_exist(
    db: AsyncSession,
    movie_ids: list[int],
) -> list[Movie]:
    """Check that all movies exist"""
    result = await db.execute(select(Movie).where(Movie.id.in_(movie_ids)))
    movies = result.scalars().all()
    if len(movies) != len(movie_ids):
        missed_ids = set(movie_ids) - {movie.id for movie in movies}
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Movie IDs not found: {missed_ids}",
        )
    return movies


async def _validate_movies_not_purchased(
    db: AsyncSession,
    user_id: int,
    movie_ids: list[int],
) -> None:
    """Check that the user has not yet purchased these movies"""
    result = await db.execute(
        select(OrderItemModel)
        .join(OrderModel)
        .where(
            and_(
                OrderModel.user_id == user_id,
                OrderModel.status == OrderStatusEnum.PAID,
                OrderItemModel.movie_id.in_(movie_ids),
            )
        )
    )
    purchased = result.scalars().all()
    if purchased:
        purchased_ids = [item.movie_id for item in purchased]
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Movies already purchased: {purchased_ids}",
        )


async def _validate_nonpaid_orders_with_same_movies(
    db: AsyncSession,
    user_id: int,
    movie_ids: list[int],
) -> None:
    """Check that the user has not yet purchased these movies"""
    result = await db.scalar(
        select(OrderItemModel)
        .join(OrderModel)
        .where(
            and_(
                OrderModel.user_id == user_id,
                OrderModel.status == OrderStatusEnum.PENDING,
                OrderItemModel.movie_id.in_(movie_ids),
            )
        )
    )
    if result:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have pending orders with the same movie ID",
        )


async def _calculate_total_amount(movies: list[Movie]) -> float:
    return sum(float(movie.price) for movie in movies)


async def _clear_user_cart(db: AsyncSession, user_id: int) -> None:
    result = await db.execute(
        select(CartItem).join(Cart).where(Cart.user_id == user_id)
    )
    cart_items = result.scalars().all()

    for item in cart_items:
        await db.delete(item)

    await db.commit()


@router.post(
    "/",
    response_model=OrderResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_order(
    order_data: OrderCreateSchema,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    movies = await _validate_movies_exist(db, order_data.movie_ids)
    await _validate_movies_not_purchased(
        db, current_user.id, order_data.movie_ids
    )
    await _validate_nonpaid_orders_with_same_movies(
        db, current_user.id, order_data.movie_ids
    )

    total_amount = await _calculate_total_amount(movies)

    order = OrderModel(
        user_id=current_user.id,
        status=OrderStatusEnum.PENDING,
        total_amount=total_amount,
    )
    db.add(order)
    await db.flush()

    for movie in movies:
        order_item = OrderItemModel(
            order_id=order.id, movie_id=movie.id, price_at_order=movie.price
        )
        db.add(order_item)

    await _clear_user_cart(db, current_user.id)

    await db.commit()
    await db.refresh(order)
    return order


@router.get(
    "/",
    response_model=OrderListResponseSchema,
    summary="Get a paginated list of orders",
    description=(
        "<h3>This endpoint retrieves a paginated list of user orders from the database. "
        "Clients can specify the `page` number and the number of items per page using `per_page`. "
        "The response includes details about the orders, total pages, and total items, "
        "along with links to the previous and next pages if applicable.</h3>"
    ),
    responses={
        404: {
            "description": "No orders found.",
            "content": {
                "application/json": {"example": {"detail": "No orders found."}}
            },
        }
    },
)
async def get_order_list(
    page: int = Query(1, ge=1, description="Page number (1-based index)"),
    per_page: int = Query(
        10, ge=1, le=20, description="Number of items per page"
    ),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrderListResponseSchema:
    offset = (page - 1) * per_page

    count_stmt = select(func.count(OrderModel.id)).where(
        OrderModel.user_id == current_user.id
    )
    result_count = await db.execute(count_stmt)
    total_items = result_count.scalar() or 0

    if not total_items:
        raise HTTPException(status_code=404, detail="No orders found.")
    order_by = OrderModel.default_order_by()
    stmt = select(OrderModel)

    if order_by:
        stmt = stmt.order_by(*order_by)
    stmt = stmt.offset(offset).limit(per_page)
    result_orders = await db.execute(stmt)
    orders = result_orders.scalars().all()

    if not orders:
        raise HTTPException(status_code=404, detail="No orders found.")
    order_list = [
        OrderListItemSchema.model_validate(order) for order in orders
    ]

    total_pages = (total_items + per_page - 1) // per_page
    per_page_param = f"per_page={per_page}"

    response = OrderListResponseSchema(
        orders=order_list,
        prev_page=(f"?page={page - 1}&{per_page_param}" if page > 1 else None),
        next_page=(
            f"?page={page + 1}&{per_page_param}"
            if page < total_pages
            else None
        ),
        total_pages=total_pages,
        total_items=total_items,
    )
    return response


@router.get(
    "/{order_id}/",
    response_model=OrderDetailResponseSchema,
    summary="Get order details by ID",
    description=(
        "<h3>Fetch detailed information about a specific order by its unique ID. "
        "This endpoint retrieves all available details for the order, such as "
        "its id, user id, creation date and time, status, total_amount, and list "
        "of its items(eg. movie title, year and genre). If the order with the given "
        "ID is not found, a 404 error will be returned.</h3>"
    ),
    responses={
        404: {
            "description": "Order not found.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Order with the given ID was not found."
                    }
                }
            },
        }
    },
)
async def get_order_by_id(
    order_id: int,
    db: AsyncSession = Depends(get_db),
) -> OrderDetailResponseSchema:
    stmt = (
        select(OrderModel)
        .options(
            joinedload(OrderModel.user),
            joinedload(OrderModel.items),
        )
        .where(OrderModel.id == order_id)
    )
    result = await db.execute(stmt)
    order = result.scalars().first()

    if not order:
        raise HTTPException(
            status_code=404, detail="Order with given ID was not found."
        )
    return OrderDetailResponseSchema.model_validate(order)


@router.patch(
    "/{order_id}/cancel/",
    response_model=OrderCancelResponseSchema,
    summary="Cancel an order",
    description="Cancel a pending order. Only the owner (or admin) can cancel it.",
)
async def cancel_order(
    order_id: int,
    cancel_data: OrderCancelRequestSchema,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(OrderModel).where(OrderModel.id == order_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.user_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="You don't have access to this order."
        )
    if order.status != OrderStatusEnum.PENDING:
        raise HTTPException(
            status_code=400,
            detail=f"Can only cancel PENDING orders. Current status: {order.status}.",
        )
    order.status = OrderStatusEnum.CANCELED
    await db.commit()
    await db.refresh(order)

    message = f"Order {order.id} was successfully cancelled"
    if cancel_data.reason:
        message += f". Reason: {cancel_data.reason}"
    return OrderCancelResponseSchema(
        id=order.id,
        user_id=order.user_id,
        created_at=order.created_at,
        status=order.status,
        total_amount=order.total_amount,
        order_items=order.items,
        message=message,
    )


@router.post("/{order_id}/confirm-payment", response_model=OrderResponseSchema)
async def confirm_payment(
    order_id: int,
    payment_data: OrderConfirmPaymentSchema,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(OrderModel).where(OrderModel.id == order_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Order not found."
        )
    if order.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this order.",
        )
    if order.status != OrderStatusEnum.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Order is already {order.status}.",
        )
    result = await db.execute(
        select(OrderItemModel).where(OrderItemModel.order_id == order_id)
    )
    order_items = result.scalars().all()

    total_check = sum(float(item.price_at_order) for item in order_items)
    if abs(total_check - float(order.total_amount)) > 0.01:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order total amount has changed.",
        )
    order.status = OrderStatusEnum.PAID
    await db.commit()
    await db.refresh(order)
    return order


@router.get(
    "/admin/all/",
    response_model=OrderListResponseSchema,
    summary="Get all orders (Admin only)",
    description=(
        "<h3>This endpoint retrieves a paginated list of ALL orders from the database. "
        "Available only for ADMIN and MODERATOR roles. "
        "Supports filtering by user_id, status, and date range. "
        "The response includes order details, total pages, total items, "
        "and links to previous/next pages if applicable.</h3>"
    ),
    responses={
        403: {
            "description": "Access forbidden. Only admins/moderators can access.",
            "content": {
                "application/json": {
                    "example": {"detail": "Only admins can view all orders"}
                }
            },
        },
        404: {
            "description": "No orders found.",
            "content": {
                "application/json": {"example": {"detail": "No orders found."}}
            },
        },
    },
)
async def get_all_orders(
    page: int = Query(1, ge=1, description="Page number (1-based index)"),
    per_page: int = Query(
        10, ge=1, le=50, description="Number of items per page"
    ),
    user_id: int = Query(None, ge=1, description="Filter by specific user ID"),
    status_filter: OrderStatusEnum = Query(
        None, description="Filter by order status"
    ),
    date_from: str = Query(
        None, description="Filter orders from date (YYYY-MM-DD)"
    ),
    date_to: str = Query(
        None, description="Filter orders to date (YYYY-MM-DD)"
    ),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrderListResponseSchema:

    if current_user.group.name not in ["ADMIN", "MODERATOR"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can view all orders.",
        )
    offset = (page - 1) * per_page

    count_stmt = select(func.count(OrderModel.id))
    stmt = select(OrderModel).where(OrderModel.user_id == current_user.id)
    filters = []

    if user_id:
        filters.append(OrderModel.user_id == user_id)

    if status_filter:
        filters.append(OrderModel.status == status_filter)

    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, "%Y-%m-%d")
            filters.append(OrderModel.created_at >= date_from_obj)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date_from format. Use YYYY-MM-DD.",
            )

    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, "%Y-%m-%d")
            filters.append(OrderModel.created_at <= date_to_obj)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date_to format. Use YYYY-MM-DD",
            )
    if filters:
        count_stmt = count_stmt.where(and_(*filters))
        stmt = stmt.where(and_(*filters))

    result_count = await db.execute(count_stmt)
    total_items = result_count.scalar() or 0

    if not total_items:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No orders found."
        )
    stmt = stmt.order_by(OrderModel.created_at.desc())

    stmt = stmt.offset(offset).limit(per_page)
    result_orders = await db.execute(stmt)
    orders = result_orders.scalars().all()

    if not orders:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No orders found."
        )

    order_list = [
        OrderResponseSchema.model_validate(order) for order in orders
    ]

    total_pages = (total_items + per_page - 1) // per_page

    base_params = []
    if user_id:
        base_params.append(f"user_id={user_id}")
    if status_filter:
        base_params.append(f"status_filter={status_filter.value}")
    if date_from:
        base_params.append(f"date_from={date_from}")
    if date_to:
        base_params.append(f"date_to={date_to}")

    base_query = "&".join(base_params)
    per_page_param = f"per_page={per_page}"

    response = OrderListResponseSchema(
        orders=order_list,
        prev_page=(
            f"?page={page - 1}&{per_page_param}"
            + (f"&{base_query}" if base_query else "")
            if page > 1
            else None
        ),
        next_page=(
            f"?page={page + 1}&{per_page_param}"
            + (f"&{base_query}" if base_query else "")
            if page < total_pages
            else None
        ),
        total_pages=total_pages,
        total_items=total_items,
    )

    return response
