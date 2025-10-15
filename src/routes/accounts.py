from datetime import datetime, timezone, timedelta
import secrets
from typing import cast

from fastapi import APIRouter, status, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

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
    MessageResponseSchema,
)
from security.passwords import hash_password
from config.settings import base_app_settings

router = APIRouter(prefix="/auth", tags=["Authentication"])


async def get_user_by_email(db: AsyncSession, email: str):
    result = await db.execute(
        select(UserModel).where(UserModel.email == email)
    )
    return result.scalar_one_or_none()


async def get_current_user(
    user_id: int, db: AsyncSession = Depends(get_postgresql_db)
):
    statement = select(UserModel).where(UserModel.id == user_id)
    result = await db.execute(statement)
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or unauthorized.",
        )
    return user


async def moderator_required(
    current_user: UserModel = Depends(get_current_user),
):
    if current_user.role not in ("moderator", "admin"):
        raise HTTPException(
            status_code=403, detail="Moderator or admin required."
        )
    return current_user


@router.post(
    "/register/",
    response_model=UserRegisterResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    user_data: UserRegisterRequestShema,
    db: AsyncSession = Depends(get_postgresql_db),
    email_sender: EmailSender = Depends(get_accounts_email_notificator),
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
            detail="User group was not found.",
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
            detail="An error occurred during user creation.",
        ) from e
    activation_link = (
        f"http://{base_app_settings.HOST_NAME}/api/v1/auth/activate/"
        f"?email={new_user.email}&token={activation_token.token}"
    )
    await email_sender.send_activation_email(new_user.email, activation_link)

    return UserRegisterResponseSchema.model_validate(new_user)


@router.get(
    "/activate/",
    response_model=MessageResponseSchema,
    status_code=status.HTTP_200_OK,
)
async def activate(
    email: str,
    token: str,
    db: AsyncSession = Depends(get_postgresql_db),
    email_sender: EmailSender = Depends(get_accounts_email_notificator),
):
    statement = (
        select(ActivationTokenModel)
        .options(joinedload(ActivationTokenModel.user))
        .join(UserModel)
        .where(
            UserModel.email == email,
            ActivationTokenModel.token == token,
        )
    )
    result = await db.execute(statement)
    token_record = result.scalars().first()

    now_utc = datetime.now(timezone.utc)
    if (
        not token_record
        or cast(datetime, token_record.expires_at).replace(tzinfo=timezone.utc)
        < now_utc
    ):
        if token_record:
            await db.delete(token_record)
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired activation token.",
            )

    user = token_record.user
    if user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is already active.",
        )

    user.is_active = True
    await db.delete(token_record)
    await db.commit()

    login_link = f"http://{base_app_settings.HOST_NAME}/api/v1/auth/login/"

    await email_sender.send_activation_complete_email(str(email), login_link)

    return MessageResponseSchema(message="User account activated.")


@router.post(
    "/resend-activation/",
    response_model=MessageResponseSchema,
    status_code=status.HTTP_200_OK,
)
async def resend_activation(
    email: str,
    db: AsyncSession = Depends(get_postgresql_db),
    email_sender: EmailSender = Depends(get_accounts_email_notificator),
):
    user = await get_user_by_email(db=db, email=email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found."
        )

    if user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already active.",
        )

    await db.execute(
        select(ActivationTokenModel).where(
            ActivationTokenModel.user_id == user.id
        )
    )
    old_token_res = await db.execute(
        select(ActivationTokenModel).where(
            ActivationTokenModel.user_id == user.id
        )
    )
    old_token = old_token_res.scalars().first()
    if old_token:
        await db.delete(old_token)

    new_token = ActivationTokenModel(
        user_id=user.id,
        token=secrets.token_urlsafe(32),
        expires_at=(datetime.utcnow() + timedelta(days=1)),
    )
    db.add(new_token)
    await db.commit()

    activation_link = (
        f"http://{base_app_settings.HOST_NAME}/api/v1/auth/activate/"
        f"?email={user.email}&token={new_token.token}"
    )
    await email_sender.send_activation_email(user.email, activation_link)

    return MessageResponseSchema(
        message="New email for account activation has been sent."
    )
