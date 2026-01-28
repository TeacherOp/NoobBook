"""
Base Repository - Abstract base class for all repositories.

Educational Note: This module defines the common interface that all
repositories must implement. Using abstract base classes ensures
consistency across different storage implementations.
"""
from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Optional, List, Dict, Any

# Type variable for entity types
T = TypeVar('T')


class BaseRepository(ABC, Generic[T]):
    """
    Abstract base repository with common CRUD operations.

    Educational Note: This base class defines the contract that all
    repository implementations must follow. Each method raises
    NotImplementedError to ensure subclasses implement them.

    Type Parameters:
        T: The entity type this repository manages
    """

    @abstractmethod
    def get_by_id(self, entity_id: str) -> Optional[T]:
        """
        Retrieve an entity by its ID.

        Args:
            entity_id: The unique identifier

        Returns:
            The entity or None if not found
        """
        raise NotImplementedError

    @abstractmethod
    def create(self, data: Dict[str, Any]) -> T:
        """
        Create a new entity.

        Args:
            data: The entity data

        Returns:
            The created entity
        """
        raise NotImplementedError

    @abstractmethod
    def update(self, entity_id: str, data: Dict[str, Any]) -> Optional[T]:
        """
        Update an existing entity.

        Args:
            entity_id: The unique identifier
            data: The fields to update

        Returns:
            The updated entity or None if not found
        """
        raise NotImplementedError

    @abstractmethod
    def delete(self, entity_id: str) -> bool:
        """
        Delete an entity by its ID.

        Args:
            entity_id: The unique identifier

        Returns:
            True if deleted, False if not found
        """
        raise NotImplementedError

    @abstractmethod
    def list_all(self, **filters) -> List[T]:
        """
        List all entities, optionally filtered.

        Args:
            **filters: Optional filter criteria

        Returns:
            List of entities matching the filters
        """
        raise NotImplementedError
