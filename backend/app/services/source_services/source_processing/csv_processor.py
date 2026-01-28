"""
CSV Processor - Handles CSV file processing.

Educational Note: CSV files are NOT chunked or embedded. Instead:
1. csv_service (AI) analyzes the CSV using csv_analyzer tool
2. AI generates a concise summary (300-400 tokens)
3. Raw CSV content is uploaded to processed storage for on-demand analysis
4. Summary is stored for context_loader to include in chat system prompts

Storage: Processed CSV is stored in Supabase Storage for on-demand queries.
The csv_tool_executor provides comprehensive analysis operations that can be
used later by the csv_analyzer_agent for detailed queries.
"""
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from app.services.integrations.supabase import storage_service
from app.services.ai_services.csv_service import csv_service


def process_csv(
    project_id: str,
    source_id: str,
    source: Dict[str, Any],
    raw_file_path: Path,
    source_service
) -> Dict[str, Any]:
    """
    Process a CSV file - AI analyzes and generates summary.

    Educational Note: Unlike other sources, CSV files are NOT embedded.
    The AI service analyzes the CSV and generates a concise summary.
    Raw CSV content is uploaded to processed storage for on-demand queries.

    Args:
        project_id: The project UUID
        source_id: The source UUID
        source: Source metadata dict
        raw_file_path: Path to the raw CSV file
        source_service: Reference to source_service for updates

    Returns:
        Dict with success status
    """
    source_name = source.get("name", "unknown")

    # Use AI service to analyze CSV and generate summary
    print(f"[CSV Processor] Analyzing {source_name} with AI service...")
    analysis_result = csv_service.analyze_csv(
        project_id=project_id,
        source_id=source_id
    )

    if not analysis_result.get("success"):
        source_service.update_source(
            project_id,
            source_id,
            status="error",
            processing_info={"error": analysis_result.get("error", "Failed to analyze CSV")}
        )
        return {"success": False, "error": analysis_result.get("error")}

    # Read CSV content and upload to processed storage
    with open(raw_file_path, "r", encoding="utf-8") as f:
        csv_content = f.read()

    storage_path = storage_service.upload_processed_file(
        project_id=project_id,
        source_id=source_id,
        content=csv_content
    )

    if not storage_path:
        source_service.update_source(
            project_id,
            source_id,
            status="error",
            processing_info={"error": "Failed to upload CSV to storage"}
        )
        return {"success": False, "error": "Failed to upload CSV to storage"}

    print(f"[CSV Processor] Uploaded CSV to Supabase Storage")

    # Build processing info from AI analysis
    processing_info = {
        "processor": "csv_processor",
        "total_rows": analysis_result.get("row_count", 0),
        "total_columns": analysis_result.get("column_count", 0),
        "iterations": analysis_result.get("iterations", 0),
        "extracted_at": datetime.now().isoformat()
    }

    # CSV files are NOT embedded - we analyze them on-demand
    embedding_info = {
        "is_embedded": False,
        "embedded_at": None,
        "token_count": 0,
        "chunk_count": 0,
        "reason": "CSV files are analyzed on-demand, not embedded"
    }

    # Summary comes from AI service (not separate summary_service)
    summary_info = {
        "summary": analysis_result.get("summary", ""),
        "model": "claude-haiku-4-5-20251001",
        "usage": analysis_result.get("usage", {}),
        "generated_at": analysis_result.get("generated_at", datetime.now().isoformat()),
        "strategy": "csv_analyzer",
        "row_count": analysis_result.get("row_count", 0),
        "column_count": analysis_result.get("column_count", 0)
    }

    source_service.update_source(
        project_id,
        source_id,
        status="ready",
        active=True,
        processing_info=processing_info,
        embedding_info=embedding_info,
        summary_info=summary_info
    )

    print(f"[CSV Processor] Completed: {source_name} ({analysis_result.get('row_count', 0)} rows, {analysis_result.get('column_count', 0)} columns)")
    return {"success": True, "status": "ready"}
