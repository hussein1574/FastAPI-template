from enum import Enum


class EnumBase(Enum):
    def __str__(self):
        return self.value
    @classmethod
    def choices(cls):
        return [role.value for role in cls]


class UserRole(EnumBase):
    ADMIN = 'admin'
    USER = 'user'

