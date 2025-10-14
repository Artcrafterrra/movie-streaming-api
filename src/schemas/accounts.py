from pydantic import BaseModel, EmailStr, ConfigDict, field_validator

from database.validators.accounts import (
    validate_password_strength,
    validate_email,
)


class UserRegisterRequestShema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, value):
        return validate_email(value.lower())

    @field_validator("password")
    @classmethod
    def validate_password(cls, value):
        return validate_password_strength(value)


class UserRegisterResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
