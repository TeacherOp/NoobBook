"""
JSON Chunk Repository - File-based implementation.

Educational Note: Chunks are stored as individual text files in
data/projects/{project_id}/sources/chunks/{source_id}/.
Each chunk file has a metadata header followed by the chunk text.
"""
import json
import re
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional, List, Dict, Any

from app.utils.path_utils import get_source_chunks_dir, get_chunks_dir
from app.repositories.chunks.interface import ChunkRepositoryInterface


class JsonChunkRepository(ChunkRepositoryInterface):
    """JSON/file-based implementation of chunk repository."""

    def _get_chunk_path(self, project_id: str, source_id: str, chunk_id: str) -> Path:
        """Get the path to a chunk file."""
        chunks_dir = get_source_chunks_dir(project_id, source_id)
        return chunks_dir / f"{chunk_id}.txt"

    def _parse_chunk_file(self, chunk_path: Path) -> Optional[Dict[str, Any]]:
        """
        Parse a chunk file into a dict.

        Chunk file format:
            # chunk_id: {id}
            # source_id: {source_id}
            # page: {N}
            # chunk: {M}
            # token_count: {count}
            # ---
            {chunk text}
        """
        if not chunk_path.exists():
            return None

        try:
            with open(chunk_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Split header and text
            if '# ---' in content:
                header, text = content.split('# ---', 1)
                text = text.strip()
            else:
                return None

            # Parse header
            metadata = {}
            for line in header.strip().split('\n'):
                if line.startswith('# ') and ':' in line:
                    key, value = line[2:].split(':', 1)
                    metadata[key.strip()] = value.strip()

            return {
                "id": metadata.get("chunk_id", chunk_path.stem),
                "source_id": metadata.get("source_id"),
                "page_number": int(metadata.get("page", 0)),
                "chunk_number": int(metadata.get("chunk", 0)),
                "token_count": int(metadata.get("token_count", 0)) if metadata.get("token_count") else None,
                "text": text
            }
        except Exception as e:
            print(f"Error parsing chunk file {chunk_path}: {e}")
            return None

    def _write_chunk_file(
        self,
        chunk_path: Path,
        chunk_id: str,
        source_id: str,
        text: str,
        page_number: int,
        chunk_number: int,
        token_count: Optional[int] = None
    ) -> bool:
        """Write a chunk file with metadata header."""
        try:
            chunk_path.parent.mkdir(parents=True, exist_ok=True)

            header_lines = [
                f"# chunk_id: {chunk_id}",
                f"# source_id: {source_id}",
                f"# page: {page_number}",
                f"# chunk: {chunk_number}",
            ]
            if token_count:
                header_lines.append(f"# token_count: {token_count}")
            header_lines.append("# ---")

            content = '\n'.join(header_lines) + '\n' + text

            with open(chunk_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        except Exception as e:
            print(f"Error writing chunk file {chunk_path}: {e}")
            return False

    def _extract_project_id_from_chunk_id(self, chunk_id: str) -> Optional[str]:
        """
        Extract project_id by searching for the chunk file.

        Educational Note: Since chunks are stored by project/source,
        we need to search to find which project contains this chunk.
        """
        # This is inefficient but maintains backward compatibility
        from config import Config
        for project_dir in Config.PROJECTS_DIR.iterdir():
            if project_dir.is_dir():
                chunks_dir = project_dir / "sources" / "chunks"
                if chunks_dir.exists():
                    for source_dir in chunks_dir.iterdir():
                        if source_dir.is_dir():
                            chunk_path = source_dir / f"{chunk_id}.txt"
                            if chunk_path.exists():
                                return project_dir.name
        return None

    # =========================================================================
    # Interface Implementation
    # =========================================================================

    def create(
        self,
        source_id: str,
        project_id: str,
        chunk_id: str,
        text: str,
        page_number: int,
        chunk_number: int,
        token_count: Optional[int] = None
    ) -> Dict[str, Any]:
        """Create a new chunk."""
        chunk_path = self._get_chunk_path(project_id, source_id, chunk_id)

        self._write_chunk_file(
            chunk_path, chunk_id, source_id, text,
            page_number, chunk_number, token_count
        )

        return {
            "id": chunk_id,
            "source_id": source_id,
            "project_id": project_id,
            "page_number": page_number,
            "chunk_number": chunk_number,
            "token_count": token_count,
            "text": text
        }

    def create_batch(self, chunks: List[Dict[str, Any]]) -> int:
        """Create multiple chunks in batch."""
        count = 0
        for chunk in chunks:
            try:
                self.create(
                    source_id=chunk["source_id"],
                    project_id=chunk["project_id"],
                    chunk_id=chunk["id"],
                    text=chunk["text"],
                    page_number=chunk["page_number"],
                    chunk_number=chunk["chunk_number"],
                    token_count=chunk.get("token_count")
                )
                count += 1
            except Exception as e:
                print(f"Error creating chunk {chunk.get('id')}: {e}")
        return count

    def get_by_id(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        """Get a chunk by its ID."""
        # Extract source_id from chunk_id (format: {source_id}_page_{N}_chunk_{M})
        match = re.match(r'^(.+)_page_\d+_chunk_\d+$', chunk_id)
        if not match:
            return None

        source_id = match.group(1)
        project_id = self._extract_project_id_from_chunk_id(chunk_id)

        if not project_id:
            return None

        chunk_path = self._get_chunk_path(project_id, source_id, chunk_id)
        chunk = self._parse_chunk_file(chunk_path)

        if chunk:
            chunk["project_id"] = project_id

        return chunk

    def get_by_source(self, source_id: str) -> List[Dict[str, Any]]:
        """Get all chunks for a source."""
        from config import Config

        chunks = []
        # Search for the source in all projects
        for project_dir in Config.PROJECTS_DIR.iterdir():
            if project_dir.is_dir():
                source_chunks_dir = project_dir / "sources" / "chunks" / source_id
                if source_chunks_dir.exists():
                    for chunk_file in source_chunks_dir.glob("*.txt"):
                        chunk = self._parse_chunk_file(chunk_file)
                        if chunk:
                            chunk["project_id"] = project_dir.name
                            chunks.append(chunk)
                    break

        # Sort by page_number, chunk_number
        return sorted(chunks, key=lambda c: (c["page_number"], c["chunk_number"]))

    def get_by_project(self, project_id: str) -> List[Dict[str, Any]]:
        """Get all chunks for a project."""
        chunks_dir = get_chunks_dir(project_id)
        chunks = []

        if chunks_dir.exists():
            for source_dir in chunks_dir.iterdir():
                if source_dir.is_dir():
                    for chunk_file in source_dir.glob("*.txt"):
                        chunk = self._parse_chunk_file(chunk_file)
                        if chunk:
                            chunk["project_id"] = project_id
                            chunks.append(chunk)

        return chunks

    def delete_by_source(self, source_id: str) -> int:
        """Delete all chunks for a source."""
        import shutil
        from config import Config

        count = 0
        for project_dir in Config.PROJECTS_DIR.iterdir():
            if project_dir.is_dir():
                source_chunks_dir = project_dir / "sources" / "chunks" / source_id
                if source_chunks_dir.exists():
                    count = len(list(source_chunks_dir.glob("*.txt")))
                    shutil.rmtree(source_chunks_dir)
                    break

        return count

    def delete_by_project(self, project_id: str) -> int:
        """Delete all chunks for a project."""
        import shutil
        chunks_dir = get_chunks_dir(project_id)
        count = 0

        if chunks_dir.exists():
            for source_dir in chunks_dir.iterdir():
                if source_dir.is_dir():
                    count += len(list(source_dir.glob("*.txt")))
            shutil.rmtree(chunks_dir)

        return count

    def search_by_keywords(
        self,
        source_id: str,
        keywords: List[str],
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search chunks by keywords using fuzzy matching.

        Educational Note: Uses difflib.SequenceMatcher for fuzzy string
        matching. This provides local keyword search for hybrid search.
        """
        chunks = self.get_by_source(source_id)

        if not keywords:
            return chunks[:limit]

        scored_chunks = []
        for chunk in chunks:
            text_lower = chunk["text"].lower()
            max_score = 0

            for keyword in keywords:
                keyword_lower = keyword.lower()
                # Direct match check
                if keyword_lower in text_lower:
                    max_score = max(max_score, 1.0)
                else:
                    # Fuzzy match for each word in the chunk
                    words = text_lower.split()
                    for word in words:
                        ratio = SequenceMatcher(None, keyword_lower, word).ratio()
                        if ratio > 0.8:  # Threshold for fuzzy match
                            max_score = max(max_score, ratio)

            if max_score > 0:
                chunk["relevance_score"] = max_score
                scored_chunks.append(chunk)

        # Sort by relevance score
        scored_chunks.sort(key=lambda c: c["relevance_score"], reverse=True)

        return scored_chunks[:limit]

    def get_chunk_count(self, source_id: str) -> int:
        """Get the number of chunks for a source."""
        chunks = self.get_by_source(source_id)
        return len(chunks)
