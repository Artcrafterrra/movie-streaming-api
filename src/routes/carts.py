from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import joinedload, selectinload

from database import get_db
from database.models.cart import Cart, CartItem
from database.models.movies import Movie
from database.models.orders import OrderModel, OrderItemModel
from database.models import UserModel
from routes.accounts import get_current_user, moderator_required
from schemas.carts import (
    AddToCartRequest,
    CartWithMovies,
    CartItemWithMovie,
    CartSummary,
    CartValidationResponse,
    AllCartsResponse,
)
from schemas.movies import MovieListResponseSchema

router = APIRouter(prefix="/cart", tags=["cart"])


async def _check_movie_already_purchased(
    user_id: int, movie_id: int, db: AsyncSession
) -> bool:
    stmt = (
        select(OrderItemModel)
        .join(OrderModel)
        .where(
            and_(
                OrderModel.user_id == user_id,
                OrderModel.status == "paid",
                OrderItemModel.movie_id == movie_id,
            )
        )
    )
    result = await db.execute(stmt)
    return result.scalars().first() is not None


@router.post("/items", status_code=status.HTTP_201_CREATED)
async def add_to_cart(
    request: AddToCartRequest,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Movie).where(Movie.id == request.movie_id)
    result = await db.execute(stmt)
    movie = result.scalars().first()

    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found"
        )

    if await _check_movie_already_purchased(
        current_user.id, request.movie_id, db
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Movie already purchased",
        )

    stmt = select(Cart).where(Cart.user_id == current_user.id)
    result = await db.execute(stmt)
    cart = result.scalars().first()

    if not cart:
        cart = Cart(user_id=current_user.id)
        db.add(cart)
        await db.commit()
        await db.refresh(cart)

    stmt = select(CartItem).where(
        and_(
            CartItem.cart_id == cart.id, CartItem.movie_id == request.movie_id
        )
    )
    result = await db.execute(stmt)
    existing_item = result.scalars().first()

    if existing_item:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Movie already in cart",
        )

    cart_item = CartItem(cart_id=cart.id, movie_id=request.movie_id)
    db.add(cart_item)
    await db.commit()

    return {"message": "Movie added to cart successfully"}


@router.get("", response_model=CartWithMovies)
async def get_cart(
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Cart)
        .options(
            joinedload(Cart.items)
            .joinedload(CartItem.movie)
            .selectinload(Movie.genres),
            joinedload(Cart.items)
            .joinedload(CartItem.movie)
            .selectinload(Movie.stars),
            joinedload(Cart.items)
            .joinedload(CartItem.movie)
            .selectinload(Movie.directors),
        )
        .where(Cart.user_id == current_user.id)
    )
    result = await db.execute(stmt)
    cart = result.scalars().first()

    if not cart:
        cart = Cart(user_id=current_user.id)
        db.add(cart)
        await db.commit()
        await db.refresh(cart)
        return CartWithMovies(
            id=cart.id,
            user_id=cart.user_id,
            items=[],
            total_items=0,
            total_price=0.0,
        )

    cart_items = []
    for item in cart.items:
        movie_schema = MovieListResponseSchema.model_validate(item.movie)
        cart_items.append(
            CartItemWithMovie(
                id=item.id,
                movie_id=item.movie_id,
                added_at=item.added_at,
                movie=movie_schema,
            )
        )

    total_price = sum(float(item.movie.price) for item in cart.items)

    return CartWithMovies(
        id=cart.id,
        user_id=cart.user_id,
        items=cart_items,
        total_items=len(cart_items),
        total_price=total_price,
    )


@router.delete("/items/{movie_id}", status_code=status.HTTP_200_OK)
async def remove_item_from_cart(
    movie_id: int,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if movie_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Movie ID must be a positive integer",
        )

    stmt = select(Cart).where(Cart.user_id == current_user.id)
    result = await db.execute(stmt)
    cart = result.scalars().first()

    if not cart:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Cart not found"
        )

    stmt = select(CartItem).where(
        and_(CartItem.cart_id == cart.id, CartItem.movie_id == movie_id)
    )
    result = await db.execute(stmt)
    cart_item = result.scalars().first()

    if not cart_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found in cart",
        )

    await db.delete(cart_item)
    await db.commit()

    return {"message": "Movie removed from cart successfully"}


@router.delete("", status_code=status.HTTP_200_OK)
async def clear_cart(
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Cart).where(Cart.user_id == current_user.id)
    result = await db.execute(stmt)
    cart = result.scalars().first()

    if not cart:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Cart not found"
        )

    # Видаляємо всі елементи з кошика
    stmt = select(CartItem).where(CartItem.cart_id == cart.id)
    result = await db.execute(stmt)
    cart_items = result.scalars().all()

    for item in cart_items:
        await db.delete(item)

    await db.commit()

    return {"message": "Cart cleared successfully"}


@router.get("/count")
async def get_cart_count(
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Cart).where(Cart.user_id == current_user.id)
    result = await db.execute(stmt)
    cart = result.scalars().first()

    if not cart:
        return {"count": 0}

    stmt = select(CartItem).where(CartItem.cart_id == cart.id)
    result = await db.execute(stmt)
    items = result.scalars().all()

    return {"count": len(items)}


@router.get("/validate", response_model=CartValidationResponse)
async def validate_cart_for_checkout(
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Cart)
        .options(joinedload(Cart.items).joinedload(CartItem.movie))
        .where(Cart.user_id == current_user.id)
    )
    result = await db.execute(stmt)
    cart = result.scalars().first()

    if not cart or not cart.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cart is empty"
        )

    validation_errors = []
    valid_items = []

    for item in cart.items:
        if not item.movie:
            validation_errors.append(
                f"Movie with ID {item.movie_id} not found"
            )
            continue

        if await _check_movie_already_purchased(
            current_user.id, item.movie_id, db
        ):
            validation_errors.append(
                f"Movie '{item.movie.name}' already purchased"
            )
            continue

        valid_items.append(item)

    movie_ids = [item.movie_id for item in cart.items]
    if len(movie_ids) != len(set(movie_ids)):
        validation_errors.append("Duplicate movies found in cart")

    total_price = sum(float(item.movie.price) for item in valid_items)

    return CartValidationResponse(
        is_valid=len(validation_errors) == 0,
        errors=validation_errors,
        valid_items_count=len(valid_items),
        total_price=total_price,
    )


@router.get("/admin/carts", response_model=AllCartsResponse)
async def get_all_carts(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(10, ge=1, le=50, description="Carts per page"),
    user_id: int = Query(None, description="Filter by user ID"),
    _: UserModel = Depends(moderator_required),
    db: AsyncSession = Depends(get_db),
):

    stmt = select(Cart).options(
        joinedload(Cart.items).joinedload(CartItem.movie)
    )

    if user_id:
        stmt = stmt.where(Cart.user_id == user_id)

    stmt = stmt.join(CartItem).distinct()

    count_stmt = select(Cart).join(CartItem).distinct()
    if user_id:
        count_stmt = count_stmt.where(Cart.user_id == user_id)

    count_result = await db.execute(count_stmt)
    total_items = len(count_result.scalars().all())

    offset = (page - 1) * per_page
    stmt = stmt.offset(offset).limit(per_page)

    result = await db.execute(stmt)
    carts = result.scalars().all()

    cart_summaries = []
    for cart in carts:
        total_price = sum(float(item.movie.price) for item in cart.items)
        cart_summaries.append(
            CartSummary(
                id=cart.id,
                user_id=cart.user_id,
                total_items=len(cart.items),
                total_price=total_price,
            )
        )

    total_pages = (total_items + per_page - 1) // per_page

    return AllCartsResponse(
        carts=cart_summaries,
        total_carts=total_items,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
    )
