from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from src.schemas.cart import CartRead, CartCreate, CartUpdate
from database.models.cart import Cart, CartItem
from src.validation.cart import cart_movie_validator

router = APIRouter()

@router.get("/cart/{cart_id}/", response_model=CartRead)
async def get_cart(cart_id: int, db: AsyncSession = Depends(get_db)) -> Cart:
    result = await db.execute(select(Cart).where(Cart.id == cart_id))
    cart = result.scalar_one_or_none()
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")
    return cart

@router.post("/carts/", response_model=CartCreate)
async def create_cart(cart: CartCreate, db: AsyncSession = Depends(get_db)) -> Cart:
    new_cart = Cart(**cart.model_dump())
    db.add(new_cart)
    await db.commit()
    await db.refresh(new_cart)
    return new_cart

@router.post("carts/{cart_id}/", response_model=CartUpdate)
async def update_cart(cart_id: int, movies: list[CartItem], db: AsyncSession = Depends(get_db)) -> Cart:
    result = await db.execute(select(Cart).where(Cart.id == cart_id))
    new_cart = result.scalars().first()
    if not new_cart:
        raise HTTPException(status_code=404, detail="Cart not found")
    movies_result = await db.execute(select(CartItem).where(CartItem.id.in_(new_cart.items_ids)))
    items = movies_result.scalars().all()
    for item in items:
        cart_movie_validator(item, new_cart)
    new_cart.items = items
    await db.commit()
    await db.refresh(new_cart)
    return new_cart

@router.delete("/carts/{cart.id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cart(cart_id: int, db: AsyncSession = Depends(get_db)) -> Cart:
    result = await db.execute(select(Cart).where(Cart.id == cart_id))
    cart = result.scalar_one_or_none()
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")
    db.delete(cart)
    await db.commit()
