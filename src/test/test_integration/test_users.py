from unittest.mock import AsyncMock

import pytest

from database import UserModel
from database.models import UserGroupModel, UserGroupEnum
from main import app
from config.dependencies import get_accounts_email_notificator


@pytest.mark.asyncio
async def test_user_register_success(client, db_session, monkeypatch):
    user_group = UserGroupModel(name=UserGroupEnum.USER)
    db_session.add(user_group)
    await db_session.commit()
    await db_session.refresh(user_group)

    mock_email_sender = AsyncMock()
    app.dependency_overrides[
        get_accounts_email_notificator
    ] = lambda: mock_email_sender

    payload = {
        "email": "user@example.com",
        "password": "userPassword!12"
    }

    response = await client.post("/api/v1/auth/register/", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "user@example.com"

    user = await db_session.get(UserModel, data["id"])
    assert user is not None
    assert user.email == "user@example.com"

    mock_email_sender.send_activation_email.assert_awaited_once()


@pytest.mark.asyncio
async def test_user_register_email_exists(client, db_session):
    user_group = UserGroupModel(name=UserGroupEnum.USER)
    db_session.add(user_group)
    await db_session.commit()
    await db_session.refresh(user_group)

    existing_user = UserModel(
        email="user@example.com",
        _hashed_password="hashedPassword",
        group_id=user_group.id
    )
    db_session.add(existing_user)
    await db_session.commit()

    payload = {"email": "user@example.com", "password": "userPassword!12"}
    response = await client.post("/api/v1/auth/register/", json=payload)

    assert response.status_code == 409
    assert response.json()["detail"] == "A user with this email already exists."


@pytest.mark.asyncio
async def test_user_register_no_user_group(client, db_session):
    payload = {
        "email": "user@example.com",
        "password": "userPassword!12"
    }
    response = await client.post("/api/v1/auth/register/", json=payload)

    assert response.status_code == 500
    assert response.json()["detail"] == "User group was not found."
    