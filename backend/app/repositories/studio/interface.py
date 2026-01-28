"""
Studio Repository Interface - Contract for studio job data access.

Educational Note: Studio jobs track content generation requests.
There are 18 different job types (audio, video, ads, etc.) that all
share a common structure but with type-specific config and output.
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any


class StudioRepositoryInterface(ABC):
    """Interface for studio job repository operations."""

    @abstractmethod
    def create_job(
        self,
        project_id: str,
        job_type: str,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new studio job.

        Args:
            project_id: The project UUID
            job_type: Type of job (audio, video, ad, flash_cards, etc.)
            config: Job-specific configuration

        Returns:
            Created job record
        """
        raise NotImplementedError

    @abstractmethod
    def get_job(
        self,
        project_id: str,
        job_id: str,
        job_type: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get a job by ID and type.

        Args:
            project_id: The project UUID
            job_id: The job UUID
            job_type: Type of job

        Returns:
            Job record or None if not found
        """
        raise NotImplementedError

    @abstractmethod
    def list_jobs(
        self,
        project_id: str,
        job_type: str
    ) -> List[Dict[str, Any]]:
        """
        List all jobs of a specific type for a project.

        Args:
            project_id: The project UUID
            job_type: Type of job

        Returns:
            List of job records, sorted by created_at (newest first)
        """
        raise NotImplementedError

    @abstractmethod
    def update_job(
        self,
        project_id: str,
        job_id: str,
        job_type: str,
        updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Update a job.

        Args:
            project_id: The project UUID
            job_id: The job UUID
            job_type: Type of job
            updates: Fields to update

        Returns:
            Updated job record or None if not found
        """
        raise NotImplementedError

    @abstractmethod
    def delete_job(
        self,
        project_id: str,
        job_id: str,
        job_type: str
    ) -> bool:
        """
        Delete a job.

        Args:
            project_id: The project UUID
            job_id: The job UUID
            job_type: Type of job

        Returns:
            True if deleted, False if not found
        """
        raise NotImplementedError

    @abstractmethod
    def update_job_status(
        self,
        project_id: str,
        job_id: str,
        job_type: str,
        status: str,
        error_message: Optional[str] = None
    ) -> bool:
        """
        Update job status.

        Args:
            project_id: The project UUID
            job_id: The job UUID
            job_type: Type of job
            status: New status (pending, processing, ready, error)
            error_message: Optional error message

        Returns:
            True if updated, False if not found
        """
        raise NotImplementedError

    @abstractmethod
    def set_job_output(
        self,
        project_id: str,
        job_id: str,
        job_type: str,
        output: Dict[str, Any],
        output_paths: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        Set job output data.

        Args:
            project_id: The project UUID
            job_id: The job UUID
            job_type: Type of job
            output: Output data (type-specific)
            output_paths: Storage paths for generated files

        Returns:
            True if updated, False if not found
        """
        raise NotImplementedError
