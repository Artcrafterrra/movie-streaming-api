from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from database.session_postgresql import get_postgresql_db as get_db
from database.models import UserModel
from routes.accounts import get_current_user

from payments.service import PaymentService
from schemas.payments import (
    PaymentCreateSchema,
    PaymentResponseSchema,
    PaymentListResponseSchema,
    PaymentCancelResponseSchema,
    PaymentRefundResponseSchema,
)

router = APIRouter(prefix="/payments", tags=["payments"])
service = PaymentService()


@router.post(
    "/orders/{order_id}",
    response_model=PaymentResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_payment_for_order(
    order_id: int,
    payment_data: PaymentCreateSchema,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    try:
        payment = await service.create_payment(
            db,
            user_id=current_user.id,
            order_id=order_id,
            amount=payment_data.amount,
            external_payment_id=payment_data.external_payment_id,
        )
        return payment
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/{payment_id}/cancel",
    response_model=PaymentCancelResponseSchema,
)
async def cancel_payment(
    payment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    try:
        payment = await service.cancel_payment(db, payment_id=payment_id)
        return PaymentCancelResponseSchema.model_validate(
            {**payment.__dict__, "message": "Payment canceled successfully"}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/{payment_id}/refund",
    response_model=PaymentRefundResponseSchema,
)
async def refund_payment(
    payment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    try:
        payment = await service.refund_payment(db, payment_id=payment_id)
        return PaymentRefundResponseSchema.model_validate(
            {**payment.__dict__, "message": "Payment refunded successfully"}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/me",
    response_model=PaymentListResponseSchema,
)
async def get_my_payments(
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    payments = await service.get_user_payments(db, user_id=current_user.id)
    return {"payments": payments}


@router.get(
    "/orders/{order_id}",
    response_model=PaymentListResponseSchema,
)
async def get_order_payments(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    payments = await service.get_order_payments(db, order_id=order_id)
    return {"payments": payments}
