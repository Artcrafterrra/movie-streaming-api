from fastapi import APIRouter, Depends, HTTPException, status
from schemas.cart import CartItemCreate
from sqlalchemy.ext.asyncio import AsyncSession
from database.models.cart import CartItem
from database import get_db
from sqlalchemy import select
from routes.accounts import get_current_user, moderator_required


router = APIRouter(tags=["Cart Items"])


@router.post(
    "/cart/items/",
    response_model=CartItemCreate,
    dependencies=[Depends(get_current_user)],
)
async def create_cart_item(
    cart_item: CartItemCreate, db: AsyncSession = Depends(get_db)
):
    new_cart_item = CartItem(**cart_item.model_dump())
    db.add(new_cart_item)
    await db.commit()
    await db.refresh(new_cart_item)
    return new_cart_item


@router.delete(
    "/cart/items/{item_id}/",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(get_current_user)],
)
async def delete_cart_item(
    cart_item_id: int, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(CartItem).where(CartItem.id == cart_item_id)
    )
    item_to_delete = result.scalar_one_or_none()
    if not item_to_delete:
        raise HTTPException(status_code=404, detail="Cart item not found")
    db.delete(item_to_delete)
    await db.commit()
