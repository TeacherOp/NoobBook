"""
Mixpanel Integration Package.

Educational Note: Provides Mixpanel analytics query access via the Service
Account REST API (HTTP Basic). Tools expose event discovery, segmentation,
funnels, retention, and cohort path analysis to chat.
"""
from app.services.integrations.knowledge_bases.mixpanel.mixpanel_service import mixpanel_service

__all__ = ["mixpanel_service"]
