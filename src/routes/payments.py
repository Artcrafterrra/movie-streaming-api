from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.accounts import UserModel, UserGroupEnum
from database.models.payments import PaymentStatusEnum
from database.session_postgresql import get_postgresql_db
from payments import PaymentService, PaymentError
from schemas.payments import PaymentCreateRequestSchema, PaymentResponseSchema


router = APIRouter(prefix="/payments", tags=["Payments"])


async def get_current_user(
    user_id: int, db: AsyncSession = Depends(get_postgresql_db)
) -> UserModel:
    result = await db.execute(select(UserModel).where(UserModel.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or unauthorized.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not active.",
        )

    return user


@router.post(
    "/",
    response_model=PaymentResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new payment",
)
async def create_payment(
    payment_data: PaymentCreateRequestSchema,
    db: AsyncSession = Depends(get_postgresql_db),
    current_user: UserModel = Depends(get_current_user),
):
    """
    Create a new payment for an order.

    - **order_id**: ID of the order to pay for
    - **amount**: Payment amount (can be partial or full)
    - **external_payment_id**: Optional external payment ID from Stripe

    Returns the created payment with status and details.
    """
    service = PaymentService()

    try:
        payment = await service.create_payment(
            db,
            user_id=current_user.id,
            order_id=payment_data.order_id,
            amount=payment_data.amount,
            external_payment_id=payment_data.external_payment_id,
            status=PaymentStatusEnum.SUCCESSFUL,
        )

        await db.commit()
        await db.refresh(payment)

        return PaymentResponseSchema.model_validate(payment)

    except PaymentError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while creating the payment: {str(e)}",
        )
