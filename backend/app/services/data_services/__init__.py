"""
Data Services - CRUD operations for data entities.

Educational Note: This folder contains services that manage data persistence
and entity lifecycle. These are NOT AI-powered services - they handle
reading, writing, and organizing data stored in JSON files.

Services:
- chat_service: Chat CRUD operations (create, list, get, update, delete)
- project_service: Project CRUD operations and settings management
- message_service: Message persistence, context building, and tool response parsing

These services typically:
- Work with JSON files for persistence
- Handle entity metadata and relationships
- Provide index management for efficient lookups
"""
from app.services.data_services.chat_service import chat_service
from app.services.data_services.project_service import ProjectService
from app.services.data_services.message_service import message_service
from app.services.data_services.database_service import database_service

# ProjectService needs to be instantiated fresh due to directory initialization
project_service = ProjectService()

__all__ = ["chat_service", "project_service", "message_service", "database_service"]
