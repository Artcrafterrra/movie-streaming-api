from datetime import datetime, timezone, timedelta
import secrets

from fastapi import APIRouter, status, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from config.dependencies import get_accounts_email_notificator
from database import (
    UserModel,
    UserGroupModel,
    UserGroupEnum,
    ActivationTokenModel,
)
from database.session_postgresql import get_postgresql_db
from notifications import EmailSender
from schemas.accounts import (
    UserRegisterResponseSchema,
    UserRegisterRequestShema,
)
from security.passwords import hash_password

router = APIRouter(prefix="/auth", tags=["Authentication"])


async def get_user_by_email(db: AsyncSession, email: str):
    result = await db.execute(
        select(UserModel).where(UserModel.email == email)
    )
    return result.scalar_one_or_none()


@router.post(
    "/register/",
    response_model=UserRegisterResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    user_data: UserRegisterRequestShema,
    db: AsyncSession = Depends(get_postgresql_db),
    email_sender: EmailSender = Depends(get_accounts_email_notificator)
):

    existing_user = await get_user_by_email(db=db, email=user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        )
    statement = select(UserGroupModel).where(
        UserGroupModel.name == UserGroupEnum.USER
    )
    result = await db.execute(statement)
    user_group = result.scalars().first()
    if not user_group:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User group was not found",
        )

    try:
        new_user = UserModel(
            email=str(user_data.email),
            _hashed_password=hash_password(user_data.password),
            group_id=user_group.id,
        )
        db.add(new_user)
        await db.flush()

        activation_token = ActivationTokenModel(
            user_id=new_user.id,
            token=secrets.token_urlsafe(32),
            expires_at=(datetime.utcnow() + timedelta(days=1)),
        )
        db.add(activation_token)

        await db.commit()
        await db.refresh(new_user)
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during user creation",
        ) from e
    activation_link = "http://localhost:8000/api/v1/auth/activate/"
    await email_sender.send_activation_email(
        new_user.email,
        activation_link
    )

    return UserRegisterResponseSchema.model_validate(new_user)


@router.post("/activate/")
async def activate():
    pass
