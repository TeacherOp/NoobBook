"""
Studio Signal Executor - Execute studio_signal tool calls from main chat.

Educational Note: This executor handles the studio_signal tool when Claude
identifies opportunities to activate studio generation options. The flow is:

1. Main chat Claude calls studio_signal tool with signals array
2. This executor validates and stores signals in Supabase studio_signals table
3. Returns "signals activated" response to Claude

Signals are stored in the studio_signals table and linked to the chat.
"""
import uuid
from datetime import datetime
from typing import Dict, Any, List

from app.services.integrations.supabase import get_supabase, is_supabase_enabled


class StudioSignalExecutor:
    """
    Executor for studio_signal tool calls.

    Educational Note: Provides immediate response to tool call while
    delegating actual signal storage to background task.
    """

    def execute(
        self,
        project_id: str,
        chat_id: str,
        signals: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Execute the studio_signal tool call.

        Educational Note: This method:
        1. Validates signals array
        2. Queues background task to store signals
        3. Returns immediate success (non-blocking)

        Args:
            project_id: The project UUID
            chat_id: The chat UUID where signals should be stored
            signals: Array of signal objects with studio_item, direction, sources

        Returns:
            Dict with immediate success response
        """
        if not signals or not isinstance(signals, list):
            return {
                "success": False,
                "message": "No signals provided"
            }

        # Validate signals structure
        valid_signals = []
        valid_items = {
            "quiz", "flash_cards", "audio_overview", "mind_map",
            "business_report", "marketing_strategy", "prd", "infographics",
            "flow_diagram", "blog", "social", "website", "email_templates",
            "components", "ads_creative", "video", "presentation", "wireframes"
        }

        for signal in signals:
            studio_item = signal.get("studio_item")
            if studio_item not in valid_items:
                print(f"Invalid studio_item: {studio_item}, skipping")
                continue

            # Build base signal
            valid_signal = {
                "id": str(uuid.uuid4()),
                "studio_item": studio_item,
                "direction": signal.get("direction", ""),
                "sources": signal.get("sources", []),
                "created_at": datetime.now().isoformat()
            }

            # Add blog-specific fields if present
            if studio_item == "blog":
                if signal.get("target_keyword"):
                    valid_signal["target_keyword"] = signal.get("target_keyword")
                if signal.get("blog_type"):
                    valid_signal["blog_type"] = signal.get("blog_type")

            # Add business_report-specific fields if present
            if studio_item == "business_report":
                if signal.get("report_type"):
                    valid_signal["report_type"] = signal.get("report_type")
                if signal.get("csv_source_ids"):
                    valid_signal["csv_source_ids"] = signal.get("csv_source_ids")
                if signal.get("context_source_ids"):
                    valid_signal["context_source_ids"] = signal.get("context_source_ids")
                if signal.get("focus_areas"):
                    valid_signal["focus_areas"] = signal.get("focus_areas")

            valid_signals.append(valid_signal)

        if not valid_signals:
            return {
                "success": False,
                "message": "No valid signals to store"
            }

        # Store signals synchronously (not background task)
        # Educational Note: We do this synchronously to avoid race conditions
        # with the main chat service which also reads/writes the chat file.
        # Signal storage is fast (just appending to JSON) so no need for background.
        activated = [s["studio_item"] for s in valid_signals]
        print(f"Storing {len(valid_signals)} studio signals: {activated}")

        store_result = self._store_signals(
            project_id=project_id,
            chat_id=chat_id,
            signals=valid_signals
        )

        if not store_result.get("success"):
            return {
                "success": False,
                "message": f"Failed to store signals: {store_result.get('error', 'Unknown error')}"
            }

        return {
            "success": True,
            "message": f"Studio signals activated: {', '.join(activated)}",
            "count": len(valid_signals)
        }

    def _store_signals(
        self,
        project_id: str,
        chat_id: str,
        signals: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Store signals in Supabase studio_signals table.

        Educational Note: Signals are stored in Supabase and linked to the chat.
        Each signal becomes a row in the studio_signals table.

        Args:
            project_id: The project UUID
            chat_id: The chat UUID
            signals: Array of validated signal objects

        Returns:
            Result dict with success status
        """
        try:
            if not is_supabase_enabled():
                return {
                    "success": False,
                    "error": "Supabase not configured"
                }

            client = get_supabase()

            # Insert each signal into studio_signals table
            inserted_count = 0
            for signal in signals:
                # Extract source_ids from sources array
                # sources is array of {source_id: "...", chunk_ids: [...]}
                # but database expects UUID[] of just source_ids
                sources = signal.get("sources", [])
                source_ids = []
                for src in sources:
                    if isinstance(src, dict) and src.get("source_id"):
                        source_ids.append(src["source_id"])
                    elif isinstance(src, str):
                        # Handle case where it's already a string
                        source_ids.append(src)

                signal_data = {
                    "chat_id": chat_id,
                    "studio_item": signal.get("studio_item"),
                    "direction": signal.get("direction", ""),
                    "source_ids": source_ids,
                    "status": "pending"
                }

                print(f"Inserting studio signal: {signal_data}")

                try:
                    response = client.table("studio_signals").insert(signal_data).execute()
                    if response.data:
                        inserted_count += 1
                        print(f"Successfully inserted signal: {response.data}")
                    else:
                        print(f"No data returned from insert")
                except Exception as insert_error:
                    print(f"Error inserting signal: {insert_error}")

            print(f"Stored {inserted_count} studio signals for chat {chat_id}")

            return {
                "success": True,
                "signals_stored": inserted_count
            }

        except Exception as e:
            print(f"Error storing studio signals: {e}")
            return {
                "success": False,
                "error": str(e)
            }


# Singleton instance
studio_signal_executor = StudioSignalExecutor()
