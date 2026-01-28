"""
Data Services - CRUD operations for data entities.

Educational Note: This folder contains services that manage data persistence
and entity lifecycle. These services use the repository pattern for data access,
enabling easy switching between JSON files and Supabase storage.

Services:
- chat_service: Chat CRUD operations (create, list, get, update, delete)
- project_service: Project CRUD operations and settings management
- message_service: Message persistence, context building, and tool response parsing

These services:
- Contain business logic for entity operations
- Delegate data access to the repository layer
- Handle entity metadata and relationships
"""
from app.services.data_services.chat_service import chat_service
from app.services.data_services.project_service import project_service
from app.services.data_services.message_service import message_service

__all__ = ["chat_service", "project_service", "message_service"]
