from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, DECIMAL
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from schemas.cart import CartRead, CartCreate, CartUpdate
from database.models.cart import Cart, CartItem
from database.models.movies import Movie
from routes.accounts import get_current_user, moderator_required
from typing import List

router = APIRouter(tags=["Cart"])


@router.get(
    "/carts/",
    response_model=CartRead,
    dependencies=[Depends(moderator_required)],
)
async def get_all_carts(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(
        10, ge=1, le=20, description="Кількість кошиків на сторінку"
    ),
    offset: int = Query(0, ge=0, description="Зсув"),
    user_id: int | None = None,
) -> List[Cart]:
    query = select(Cart).offset(offset).limit(limit)
    if user_id:
        query = query.where(Cart.user_id == user_id)
    result = await db.execute(query.offset(offset).limit(limit))
    return result.scalars().all()


@router.get(
    "/cart/{cart_id}/",
    response_model=CartRead,
    dependencies=[Depends(get_current_user)],
)
async def get_cart(
    cart_id: int,
    db: AsyncSession = Depends(get_db),
    limit: int = Query(
        5, ge=1, le=10, description="Кількість кошиків на сторінку"
    ),
    offset: int = Query(0, ge=0, description="Зсув"),
    movie_name: str | None = None,
    movie_year: int | None = None,
    movie_min_imdb: float | None = None,
    movie_min_price: DECIMAL | None = None,
    movie_max_price: DECIMAL | None = None,
) -> Cart:
    query = select(CartItem).where(CartItem.cart_id == cart_id)
    if movie_name:
        query = query.join(CartItem.movie).where(
            Movie.name.ilike(f"%{movie_name}%")
        )
    if movie_year:
        query = query.join(CartItem.movie).where(Movie.year == movie_year)
    if movie_min_imdb:
        query = query.join(CartItem.movie).where(Movie.imdb >= movie_min_imdb)
    if movie_min_price:
        query = query.join(CartItem.movie).where(
            Movie.price >= movie_min_price
        )
    if movie_max_price:
        query = query.join(CartItem.movie).where(
            Movie.price <= movie_max_price
        )
    result = await db.execute(query.offset(offset).limit(limit))
    cart = result.scalars().all()
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")
    return cart


@router.post(
    "/carts/",
    response_model=CartCreate,
    dependencies=[Depends(get_current_user)],
)
async def create_cart(
    cart: CartCreate, db: AsyncSession = Depends(get_db)
) -> Cart:
    new_cart = Cart(**cart.model_dump())
    db.add(new_cart)
    await db.commit()
    await db.refresh(new_cart)
    return new_cart


@router.patch(
    "/carts/{card_id}/",
    response_model=CartUpdate,
    dependencies=[Depends(get_current_user)],
)
async def clear_cart(cart_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Cart).where(Cart.id == cart_id))
    new_cart = result.scalar_one_or_none()
    if not new_cart:
        raise HTTPException(status_code=404, detail="Cart not found")
    new_cart.items = None
    await db.commit()
    await db.refresh(new_cart)
    return new_cart


@router.delete(
    "/carts/{cart_id}/",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(get_current_user)],
)
async def delete_cart(cart_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Cart).where(Cart.id == cart_id))
    cart = result.scalar_one_or_none()
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")
    db.delete(cart)
    await db.commit()
