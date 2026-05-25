"""
XLSX Processor — convert Excel workbooks into CSV and reuse the CSV pipeline.

Why route through csv_processor: the chat-side analyzer (csv_analyzer_agent)
dispatches on `embedding_info["file_extension"] == ".csv"` and the existing
csv_service prompts are already tuned for tabular data. Re-implementing all
of that for xlsx would be churn for no gain.

Multi-sheet handling: each sheet is dumped as its own CSV section with a
clear `=== SHEET: <name> ===` header so the analyzer can tell sheets
apart. Sheets are concatenated in workbook order. For a single-sheet
workbook the header is omitted so it looks identical to a plain CSV.

Empty sheets are skipped. Cells are coerced to strings via pandas'
default csv export — dates and numbers round-trip cleanly enough for
the analyzer's purposes.
"""
import logging
from io import StringIO
from pathlib import Path
from typing import Dict, Any

import pandas as pd

from app.services.integrations.supabase import storage_service
from app.services.source_services.source_processing.csv_processor import process_csv

logger = logging.getLogger(__name__)


def _xlsx_to_csv_text(xlsx_path: Path) -> str:
    """Read every sheet in the workbook and return a single CSV string."""
    # sheet_name=None returns {sheet_name: DataFrame} preserving workbook order.
    sheets: Dict[str, pd.DataFrame] = pd.read_excel(xlsx_path, sheet_name=None)
    non_empty = [(name, df) for name, df in sheets.items() if not df.empty]

    if not non_empty:
        return ''

    buf = StringIO()
    if len(non_empty) == 1:
        non_empty[0][1].to_csv(buf, index=False)
        return buf.getvalue()

    for idx, (name, df) in enumerate(non_empty):
        if idx > 0:
            buf.write('\n')
        buf.write(f"=== SHEET: {name} ===\n")
        df.to_csv(buf, index=False)
    return buf.getvalue()


def process_xlsx(
    project_id: str,
    source_id: str,
    source: Dict[str, Any],
    raw_file_path: Path,
    source_service,
) -> Dict[str, Any]:
    source_name = source.get("name", "unknown")
    logger.info("Processing XLSX source: %s", source_name)

    try:
        csv_text = _xlsx_to_csv_text(raw_file_path)
    except Exception as exc:
        logger.error("Failed to read XLSX %s: %s", raw_file_path, exc)
        source_service.update_source(
            project_id,
            source_id,
            status="error",
            processing_info={"error": f"Failed to read XLSX: {exc}"},
        )
        return {"success": False, "error": f"Failed to read XLSX: {exc}"}

    if not csv_text.strip():
        source_service.update_source(
            project_id,
            source_id,
            status="error",
            processing_info={"error": "Workbook is empty (no sheets with data)"},
        )
        return {"success": False, "error": "Workbook is empty"}

    # Write the converted CSV next to the raw xlsx so csv_processor reads
    # from disk via its usual path. Keeping it inside the same per-source
    # temp dir means the outer cleanup in source_processing_service still
    # removes it on completion.
    csv_path = raw_file_path.with_suffix('.csv')
    csv_path.write_text(csv_text, encoding='utf-8')

    # Also persist the converted CSV in the raw-files bucket as
    # `{source_id}.csv`. The chat-side csv_analyzer downloads the data via
    # `storage_service.download_raw_file(project_id, source_id, f"{source_id}.csv")`
    # (analysis_executor.py:75-83). For native-CSV uploads that object
    # lands there naturally at upload time; for XLSX-converted sources the
    # only object in raw-files is `{source_id}.xlsx`, so without this step
    # every chat question 404s and the analyzer falls back to a low-quality
    # answer hallucinated from the source summary. Production logs from
    # 2026-05-25 captured 5 sources hitting that loop before the user
    # gave up and re-uploaded as .csv.
    # upload_raw_file catches all exceptions internally and returns None on
    # failure (logging the cause with full context), so no try/except needed
    # here — the None-check below is the only branch that can ever fire.
    raw_csv_path = storage_service.upload_raw_file(
        project_id=project_id,
        source_id=source_id,
        filename=f"{source_id}.csv",
        file_data=csv_text.encode('utf-8'),
        content_type='text/csv; charset=utf-8',
    )
    if not raw_csv_path:
        source_service.update_source(
            project_id,
            source_id,
            status='error',
            processing_info={
                'error': (
                    'Converted CSV could not be uploaded to storage. '
                    'Retry the source or re-upload the XLSX.'
                )
            },
        )
        return {'success': False, 'error': 'Failed to upload converted CSV to storage'}

    return process_csv(project_id, source_id, source, csv_path, source_service)
