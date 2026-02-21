from datetime import datetime, timezone
from typing import Optional
from uuid import UUID
from sqlalchemy import DateTime, ForeignKey, Integer, func, select

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession, AsyncEngine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from app.core.config import get_settings



# ==================================================================
# DECLARATIVE BASE
# ==================================================================
class Base(DeclarativeBase): pass


# ==================================================================
# MIXINS
# ==================================================================

class SoftDeleteMixin:
    """
    Adds soft delete capability to models.
    """
    
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None
    )
    
    deleted_by: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        default=None
    )
    
    def soft_delete(self, deleted_by_user_id: UUID) -> None:
        """Soft delete this entity."""
        self.deleted_at = datetime.now(timezone.utc)
        self.deleted_by = deleted_by_user_id
    
    def restore(self) -> None:
        """Restore a soft-deleted entity."""
        self.deleted_at = None
        self.deleted_by = None
    
    @property
    def is_deleted(self) -> bool:
        """Check if entity is soft-deleted."""
        return self.deleted_at is not None


class AuditMixin:
    """
    Tracks who created and last updated each record.
    """
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now()
    )
    
    created_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False
    )
    
    updated_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False
    )


class OrderedMixin:
    """
    Enables drag-and-drop reordering within a parent entity.
    """
    
    order_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )
    
    @classmethod
    async def get_next_order_index(
        cls,
        session: AsyncSession,
        parent_id: UUID,
        parent_field: str
    ) -> int:
        """Get the next available order_index for a new item."""
        stmt = (
            select(func.max(cls.order_index))
            .where(getattr(cls, parent_field) == parent_id)
        )
        
        if hasattr(cls, 'deleted_at'):
            stmt = stmt.where(cls.deleted_at.is_(None))
        
        result = await session.execute(stmt)
        max_index = result.scalar()
        
        return (max_index + 1) if max_index is not None else 0
    
    async def reorder(
        self,
        session: AsyncSession,
        new_position: int,
        parent_id: UUID,
        parent_field: str
    ) -> None:
        """Move this item to a new position, shifting others as needed."""
        old_position = self.order_index
        
        if old_position == new_position:
            return
        
        model_class = self.__class__
        
        base_query = (
            select(model_class)
            .where(getattr(model_class, parent_field) == parent_id)
            .with_for_update()
        )
        
        if hasattr(model_class, 'deleted_at'):
            base_query = base_query.where(model_class.deleted_at.is_(None))
        
        result = await session.execute(base_query)
        items = result.scalars().all()
        
        other_items = [item for item in items if item.order_index != old_position]
        
        if new_position < old_position:
            for item in other_items:
                if new_position <= item.order_index < old_position:
                    item.order_index += 1
        else:
            for item in other_items:
                if old_position < item.order_index <= new_position:
                    item.order_index -= 1
        
        self.order_index = new_position


class CollaborativeMixin:
    """Permission checking helper for collaborative entities."""
    
    ROLE_HIERARCHY = {
        'owner': 3,
        'editor': 2,
        'viewer': 1
    }
    
    @staticmethod
    def has_sufficient_role(user_role: str, required_role: str) -> bool:
        """Check if user's role meets minimum requirement."""
        hierarchy = CollaborativeMixin.ROLE_HIERARCHY
        return hierarchy.get(user_role, 0) >= hierarchy.get(required_role, 0)


# ==================================================================
# DATABASE ENGINE & SESSION FACTORY
# ==================================================================

_engine: AsyncEngine | None = None
_async_session_local: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(get_settings().DATABASE_URL)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _async_session_local
    if _async_session_local is None:
        _async_session_local = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session_local


# Alias for backward compatibility (used by cleanup_tokens.py)
def AsyncSessionLocal() -> AsyncSession:
    return get_session_factory()()


# The Dependency
async def get_db():
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()