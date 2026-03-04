"""
Component Agent Executor - Handles studio signal execution for UI components.

Educational Note: This executor is triggered by studio signals (from main chat)
and launches the component agent as a background task to generate 2-4 component variations.
"""

import logging
from typing import Dict, Any, Optional
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)


class ComponentAgentExecutor:
    """
    Executor for UI component generation via studio signals.

    Educational Note: The studio signal flow:
    1. User chats with AI about creating components
    2. AI decides to activate studio (sends studio_signal tool call)
    3. studio_signal_executor routes to this executor
    4. We create a job and launch component_agent as background task
    5. Agent runs independently and updates job status
    6. Agent generates 2-4 variations of the requested component
    """

    def execute(
        self,
        project_id: str,
        source_id: str,
        direction: str = "",
        user_id: str = None,
        previous_components: Optional[Dict] = None,
        edit_instructions: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute component generation as a background task.

        Args:
            project_id: The project ID
            source_id: Source to generate components from
            direction: User's direction/guidance for the components
            user_id: The authenticated user's UUID (for brand config lookup)

        Returns:
            Job info with status and job_id for polling
        """
        from app.services.studio_services import studio_index_service
        from app.services.background_services import task_service
        from app.services.ai_agents.component_agent_service import component_agent_service
        from app.services.source_services import source_service

        # Get source info
        source = source_service.get_source(project_id, source_id)
        if not source:
            return {
                "success": False,
                "error": f"Source {source_id} not found"
            }

        source_name = source.get("name", "Unknown Source")

        # Create job
        job_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()

        studio_index_service.create_component_job(
            project_id=project_id,
            job_id=job_id,
            source_id=source_id,
            source_name=source_name,
            direction=direction
        )

        # Launch agent as background task
        def run_agent():
            """Background task to run the component agent."""
            logger.info("Starting component agent for job %s", job_id[:8])
            try:
                component_agent_service.generate_components(
                    project_id=project_id,
                    source_id=source_id,
                    job_id=job_id,
                    direction=direction,
                    user_id=user_id,
                    previous_components=previous_components,
                    edit_instructions=edit_instructions
                )
            except Exception as e:
                logger.exception("Component agent failed for job %s", job_id[:8])
                # Update job on error
                studio_index_service.update_component_job(
                    project_id, job_id,
                    status="error",
                    error_message=str(e)
                )

        task_service.submit_task(
            task_type="component_generation",
            target_id=job_id,
            callable_func=run_agent
        )

        return {
            "success": True,
            "job_id": job_id,
            "status": "processing",
            "message": f"Component generation started for '{source_name}'"
        }


# Singleton instance
component_agent_executor = ComponentAgentExecutor()
