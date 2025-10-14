from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from src.schemas.cart import CartRead, CartCreate
from database.models.cart import Cart

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
