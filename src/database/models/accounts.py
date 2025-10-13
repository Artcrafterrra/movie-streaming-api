from enum import Enum


class UserGroupEnum(Enum):
    USER = "user"
    MODERATOR = "moderator"
    ADMIN = "admin"


class GenderEnum(Enum):
    MAN = "man"
    WOMAN = "woman"
