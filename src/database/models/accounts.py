from database.models.base import Base
from datetime import datetime, date, timezone, timedelta
import enum
from typing import Optional

from sqlalchemy import (
    String,
    Boolean,
    DateTime,
    ForeignKey,
    func,
    Integer,
    Date,
    Text,
    Enum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from database.validators.accounts import validate_email


class UserGroupEnum(str, enum.Enum):
    USER = "user"
    MODERATOR = "moderator"
    ADMIN = "admin"


class GenderEnum(str, enum.Enum):
    MAN = "man"
    WOMAN = "woman"


class UserGroupModel(Base):
    __tablename__ = "user_groups"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    name: Mapped[UserGroupEnum] = mapped_column(
        Enum(UserGroupEnum), nullable=False, unique=True
    )

    users: Mapped[list["UserModel"]] = relationship(
        "UserModel", back_populates="group"
    )

    def __repr__(self):
        return f"<UserGroupModel(id={self.id}, name={self.name})>"


class UserModel(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False
    )
    _hashed_password: Mapped[str] = mapped_column(
        "hashed_password", String(255), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    group_id: Mapped[int] = mapped_column(
        ForeignKey("user_groups.id", ondelete="CASCADE"), nullable=False
    )
    group: Mapped[UserGroupModel] = relationship(
        "UserGroupModel", back_populates="users"
    )

    activation_token: Mapped[Optional["ActivationTokenModel"]] = relationship(
        "ActivationTokenModel",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    password_reset_token: Mapped[Optional["PasswordResetTokenModel"]] = (
        relationship(
            "PasswordResetTokenModel",
            back_populates="user",
            uselist=False,
            cascade="all, delete-orphan",
        )
    )

    refresh_token: Mapped[list["RefreshTokenModel"]] = relationship(
        "RefreshTokenModel",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    profile: Mapped[Optional["UserProfileModel"]] = relationship(
        "UserProfileModel", back_populates="user", uselist=False
    )

    def __repr__(self):
        return f"<UserModel(id={self.id}, email={self.email}, is_active={self.is_active})>"

    def has_group(self, group_name: UserGroupEnum) -> bool:
        return self.group.name == group_name

    @validates("email")
    def validate_email(self, key, value) -> str:
        return validate_email(value.lower())


class UserProfileModel(Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    first_name: Mapped[Optional[str]] = mapped_column(String(100))
    last_name: Mapped[Optional[str]] = mapped_column(String(100))
    avatar: Mapped[Optional[str]] = mapped_column(String(255))
    gender: Mapped[Optional[GenderEnum]] = mapped_column(Enum(GenderEnum))
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date)
    info: Mapped[Optional[str]] = mapped_column(Text)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    user: Mapped[UserModel] = relationship(
        "UserModel", back_populates="profile"
    )

    def __repr__(self):
        return (
            f"<UserProfileModel(id={self.id}, first_name={self.first_name}, last_name={self.last_name}, "
            f"gender={self.gender}, date_of_birth={self.date_of_birth})>"
        )


class TokenBaseModel(Base):
    __abstract__ = True

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    token: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc) + timedelta(days=1),
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )


class ActivationTokenModel(TokenBaseModel):
    __tablename__ = "activation_tokens"

    user: Mapped[UserModel] = relationship(
        "UserModel", back_populates="activation_token"
    )

    def __repr__(self):
        return f"<ActivationTokenModel(id={self.id}, token={self.token}, expires_at={self.expires_at})>"


class PasswordResetTokenModel(TokenBaseModel):
    __tablename__ = "password_reset_tokens"

    user: Mapped[UserModel] = relationship(
        "UserModel", back_populates="password_reset_token"
    )

    def __repr__(self):
        return f"<PasswordResetTokenModel(id={self.id}, token={self.token}, expires_at={self.expires_at})>"


class RefreshTokenModel(TokenBaseModel):
    __tablename__ = "refresh_tokens"

    user: Mapped[UserModel] = relationship(
        "UserModel", back_populates="refresh_token"
    )

    def __repr__(self):
        return f"<RefreshTokenModel(id={self.id}, token={self.token}, expires_at={self.expires_at})>"
