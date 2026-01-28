"""
JSON Studio Repository - File-based implementation.

Educational Note: Studio jobs are stored in data/projects/{project_id}/studio/studio_index.json.
The index has separate arrays for each job type (audio_jobs, video_jobs, etc.).
"""
import json
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from app.utils.path_utils import get_studio_dir
from app.repositories.studio.interface import StudioRepositoryInterface


# Mapping from job_type to index key
JOB_TYPE_TO_KEY = {
    "audio": "audio_jobs",
    "video": "video_jobs",
    "ad": "ad_jobs",
    "flash_cards": "flash_card_jobs",
    "mind_map": "mind_map_jobs",
    "quiz": "quiz_jobs",
    "social_post": "social_post_jobs",
    "infographic": "infographic_jobs",
    "email": "email_jobs",
    "website": "website_jobs",
    "component": "component_jobs",
    "flow_diagram": "flow_diagram_jobs",
    "wireframe": "wireframe_jobs",
    "presentation": "presentation_jobs",
    "prd": "prd_jobs",
    "marketing_strategy": "marketing_strategy_jobs",
    "blog": "blog_jobs",
    "business_report": "business_report_jobs"
}


class JsonStudioRepository(StudioRepositoryInterface):
    """JSON file-based implementation of studio repository."""

    def _get_index_path(self, project_id: str):
        """Get the studio index file path."""
        return get_studio_dir(project_id) / "studio_index.json"

    def _load_index(self, project_id: str) -> Dict[str, Any]:
        """Load the studio index for a project."""
        index_path = self._get_index_path(project_id)

        default_index = {key: [] for key in JOB_TYPE_TO_KEY.values()}
        default_index["last_updated"] = datetime.now().isoformat()

        if not index_path.exists():
            return default_index

        try:
            with open(index_path, 'r') as f:
                data = json.load(f)
                # Ensure all job type arrays exist
                for key in JOB_TYPE_TO_KEY.values():
                    if key not in data:
                        data[key] = []
                return data
        except (json.JSONDecodeError, FileNotFoundError):
            return default_index

    def _save_index(self, project_id: str, index_data: Dict[str, Any]) -> None:
        """Save the studio index."""
        index_path = self._get_index_path(project_id)
        index_path.parent.mkdir(parents=True, exist_ok=True)

        index_data["last_updated"] = datetime.now().isoformat()
        with open(index_path, 'w') as f:
            json.dump(index_data, f, indent=2)

    def _get_jobs_key(self, job_type: str) -> str:
        """Get the index key for a job type."""
        return JOB_TYPE_TO_KEY.get(job_type, f"{job_type}_jobs")

    # =========================================================================
    # Interface Implementation
    # =========================================================================

    def create_job(
        self,
        project_id: str,
        job_type: str,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a new studio job."""
        job_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        job = {
            "id": job_id,
            "status": "pending",
            "config": config or {},
            "output": {},
            "output_paths": {},
            "created_at": now,
            "updated_at": now
        }

        index = self._load_index(project_id)
        jobs_key = self._get_jobs_key(job_type)
        index[jobs_key].append(job)
        self._save_index(project_id, index)

        return job

    def get_job(
        self,
        project_id: str,
        job_id: str,
        job_type: str
    ) -> Optional[Dict[str, Any]]:
        """Get a job by ID and type."""
        index = self._load_index(project_id)
        jobs_key = self._get_jobs_key(job_type)

        for job in index.get(jobs_key, []):
            if job["id"] == job_id:
                return job
        return None

    def list_jobs(
        self,
        project_id: str,
        job_type: str
    ) -> List[Dict[str, Any]]:
        """List all jobs of a specific type."""
        index = self._load_index(project_id)
        jobs_key = self._get_jobs_key(job_type)
        jobs = index.get(jobs_key, [])

        return sorted(
            jobs,
            key=lambda j: j.get("created_at", ""),
            reverse=True
        )

    def update_job(
        self,
        project_id: str,
        job_id: str,
        job_type: str,
        updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update a job."""
        index = self._load_index(project_id)
        jobs_key = self._get_jobs_key(job_type)

        for i, job in enumerate(index.get(jobs_key, [])):
            if job["id"] == job_id:
                for key, value in updates.items():
                    if value is not None:
                        job[key] = value
                job["updated_at"] = datetime.now().isoformat()
                index[jobs_key][i] = job
                self._save_index(project_id, index)
                return job

        return None

    def delete_job(
        self,
        project_id: str,
        job_id: str,
        job_type: str
    ) -> bool:
        """Delete a job."""
        index = self._load_index(project_id)
        jobs_key = self._get_jobs_key(job_type)

        original_count = len(index.get(jobs_key, []))
        index[jobs_key] = [j for j in index.get(jobs_key, []) if j["id"] != job_id]

        if len(index[jobs_key]) < original_count:
            self._save_index(project_id, index)
            return True
        return False

    def update_job_status(
        self,
        project_id: str,
        job_id: str,
        job_type: str,
        status: str,
        error_message: Optional[str] = None
    ) -> bool:
        """Update job status."""
        updates = {"status": status}
        if error_message:
            updates["error_message"] = error_message
        if status == "ready":
            updates["completed_at"] = datetime.now().isoformat()

        result = self.update_job(project_id, job_id, job_type, updates)
        return result is not None

    def set_job_output(
        self,
        project_id: str,
        job_id: str,
        job_type: str,
        output: Dict[str, Any],
        output_paths: Optional[Dict[str, str]] = None
    ) -> bool:
        """Set job output data."""
        updates = {"output": output}
        if output_paths:
            updates["output_paths"] = output_paths

        result = self.update_job(project_id, job_id, job_type, updates)
        return result is not None
