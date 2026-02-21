from typing import Generic, TypeVar, Type, Optional, List
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    Base repository providing common CRUD operations.
    
    Usage:
        class WorldRepository(BaseRepository[World]):
            def __init__(self, db: AsyncSession):
                super().__init__(db, World)
            
            # Add custom methods here
            async def get_by_name(self, name: str):
                ...
    """
    
    def __init__(self, db: AsyncSession, model: Type[ModelType]):
        """
        Initialize repository.
        
        Args:
            db: Async database session
            model: SQLAlchemy model class
        """
        self.db = db
        self.model = model
    
    async def create(self, entity: ModelType) -> ModelType:
        """Create a new entity."""
        self.db.add(entity)
        await self.db.flush()
        await self.db.refresh(entity)
        return entity
    
    async def update(self, entity: ModelType) -> ModelType:
        """Update an existing entity."""
        await self.db.flush()
        await self.db.refresh(entity)
        return entity
    
    async def delete(self, entity: ModelType) -> None:
        """Hard delete an entity (permanent)."""
        await self.db.delete(entity)
        await self.db.flush()
    
    async def get_by_id(
        self,
        entity_id: UUID,
        include_deleted: bool = False
    ) -> Optional[ModelType]:
        """
        Get entity by ID.
        
        Args:
            entity_id: Entity UUID
            include_deleted: Whether to include soft-deleted entities
        
        Returns:
            Entity if found, None otherwise
        """
        query = select(self.model).where(self.model.id == entity_id)
        
        # Filter out soft-deleted entities
        if not include_deleted and hasattr(self.model, 'deleted_at'):
            query = query.where(self.model.deleted_at.is_(None))
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_all(
        self,
        include_deleted: bool = False,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        **filters
    ) -> List[ModelType]:
        """
        Get all entities matching filters.
        
        Args:
            include_deleted: Whether to include soft-deleted entities
            limit: Maximum number of results
            offset: Number of results to skip
            **filters: Field filters (e.g., owner_id=uuid)
        
        Returns:
            List of entities
        
        Example:
            books = await repo.get_all(owner_id=user_id, limit=10)
        """
        query = select(self.model)
        
        # Apply soft delete filter
        if not include_deleted and hasattr(self.model, 'deleted_at'):
            query = query.where(self.model.deleted_at.is_(None))
        
        # Apply custom filters
        for field, value in filters.items():
            if hasattr(self.model, field):
                query = query.where(getattr(self.model, field) == value)
        
        # Apply pagination
        if limit is not None:
            query = query.limit(limit)
        if offset is not None:
            query = query.offset(offset)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_with_parent_check(
        self,
        child_id: UUID,
        parent_model: Type[Base],
        parent_fk: str
    ) -> Optional[ModelType]:
        """
        Get child entity, verifying parent is not soft-deleted.
        
        Args:
            child_id: Child entity UUID
            parent_model: Parent model class (e.g., Book for Chapter)
            parent_fk: FK field name on child (e.g., "book_id")
        
        Returns:
            Child if both child and parent are not deleted, None otherwise
        
        Example:
            chapter = await repo.get_with_parent_check(
                child_id=chapter_id,
                parent_model=Book,
                parent_fk="book_id"
            )
        """
        query = (
            select(self.model)
            .join(parent_model, getattr(self.model, parent_fk) == parent_model.id)
            .where(self.model.id == child_id)
        )
        
        # Check child is not deleted
        if hasattr(self.model, 'deleted_at'):
            query = query.where(self.model.deleted_at.is_(None))
        
        # Check parent is not deleted
        if hasattr(parent_model, 'deleted_at'):
            query = query.where(parent_model.deleted_at.is_(None))
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def count(self, include_deleted: bool = False, **filters) -> int:
        """
        Count entities matching filters.
        
        Args:
            include_deleted: Whether to include soft-deleted entities
            **filters: Field filters
        
        Returns:
            Count of matching entities
        """
        query = select(func.count()).select_from(self.model)
        
        if not include_deleted and hasattr(self.model, 'deleted_at'):
            query = query.where(self.model.deleted_at.is_(None))
        
        for field, value in filters.items():
            if hasattr(self.model, field):
                query = query.where(getattr(self.model, field) == value)
        
        result = await self.db.execute(query)
        return result.scalar()