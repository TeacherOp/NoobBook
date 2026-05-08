"""
Tests for the chat-attachment plumbing.

Covers:
  - The frontend formatter `_format_message_for_frontend` rendering image
    blocks alongside text instead of stripping them as if they were tool
    blocks.
  - `_rewrite_image_blocks_for_claude` translating persisted
    `{type:"image", storage_path:...}` blocks into Claude's vision shape
    `{type:"image", source:{type:"base64", media_type, data}}`.
  - Pure text content untouched by either pass (backwards compat).
  - Failure mode: when the storage download returns None, the image
    block is dropped rather than crashing the whole request.
"""
import base64
from unittest.mock import patch

import pytest

from app.services.data_services.message_service import MessageService


@pytest.fixture
def service():
    """A MessageService instance with the supabase client unwired — the
    methods under test don't touch the DB."""
    svc = MessageService.__new__(MessageService)
    svc.supabase = None  # type: ignore[attr-defined]
    svc.table = "messages"  # type: ignore[attr-defined]
    svc.chats_table = "chats"  # type: ignore[attr-defined]
    return svc


# ==========================================================================
# _format_message_for_frontend — image blocks survive
# ==========================================================================


class TestFormatForFrontendImageBlocks:

    def test_text_only_message_keeps_string_shape(self, service):
        """Pure-text user messages must continue to render as plain string
        content for backwards compatibility with every existing chat in
        the DB."""
        msg = {
            "id": "m1",
            "role": "user",
            "content": {"text": "Hello world"},
            "created_at": "2026-05-08T00:00:00Z",
        }
        out = service._format_message_for_frontend(msg)
        assert out["content"] == "Hello world"
        assert out["error"] is False

    def test_block_content_with_image_returns_typed_blocks(self, service):
        """When the persisted content is a list with image blocks, the
        formatter returns a typed-block list — not a flat string — so
        the chat-bubble renderer can show the image alongside text."""
        with patch(
            "app.services.integrations.supabase.storage_service.get_chat_attachment_url",
            return_value="https://signed.example.com/abc.png",
        ):
            msg = {
                "id": "m1",
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "storage_path": "p1/c1/att1/screenshot.png",
                        "media_type": "image/png",
                        "filename": "screenshot.png",
                    },
                    {"type": "text", "text": "What's in this?"},
                ],
                "created_at": "2026-05-08T00:00:00Z",
            }
            out = service._format_message_for_frontend(msg)
        assert isinstance(out["content"], list)
        # Image block re-signed with a fresh URL, internal storage_path stripped
        assert out["content"][0] == {
            "type": "image",
            "url": "https://signed.example.com/abc.png",
            "media_type": "image/png",
            "filename": "screenshot.png",
        }
        assert out["content"][1] == {"type": "text", "text": "What's in this?"}

    def test_block_content_without_images_falls_back_to_text(self, service):
        """Tool-use / tool-result blocks (no image) keep the legacy text-
        join behaviour."""
        msg = {
            "id": "m1",
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Hello"},
                {"type": "tool_use", "name": "search_sources"},
                {"type": "text", "text": "World"},
            ],
            "created_at": "2026-05-08T00:00:00Z",
        }
        out = service._format_message_for_frontend(msg)
        assert out["content"] == "Hello\n\nWorld"


# ==========================================================================
# _rewrite_image_blocks_for_claude — vision-shape translation
# ==========================================================================


class TestRewriteImageBlocksForClaude:

    def test_pure_string_content_unchanged(self, service):
        assert service._rewrite_image_blocks_for_claude("hi") == "hi"

    def test_dict_text_content_unchanged(self, service):
        # build_api_messages handles the dict→string extraction before
        # this runs; the rewriter shouldn't touch dicts.
        original = {"text": "hi"}
        assert service._rewrite_image_blocks_for_claude(original) == original

    def test_text_only_list_unchanged(self, service):
        """Lists without any image blocks are returned without traversal —
        important so tool_use/tool_result message chains keep working."""
        original = [
            {"type": "text", "text": "Hello"},
            {"type": "tool_use", "id": "tu_1", "name": "x", "input": {}},
        ]
        assert service._rewrite_image_blocks_for_claude(original) is original

    def test_image_block_rewritten_to_base64_source(self, service):
        """Persisted storage_path image block becomes Claude's vision
        shape with inline base64."""
        png_bytes = b"\x89PNG\r\n\x1a\n" + b"x" * 32
        with patch(
            "app.services.integrations.supabase.storage_service.download_chat_attachment",
            return_value=png_bytes,
        ):
            content = [
                {
                    "type": "image",
                    "storage_path": "p1/c1/att1/screenshot.png",
                    "media_type": "image/png",
                    "filename": "screenshot.png",
                },
                {"type": "text", "text": "What's in this?"},
            ]
            out = service._rewrite_image_blocks_for_claude(content)
        assert out[0]["type"] == "image"
        assert out[0]["source"]["type"] == "base64"
        assert out[0]["source"]["media_type"] == "image/png"
        assert out[0]["source"]["data"] == base64.standard_b64encode(png_bytes).decode("ascii")
        # storage_path / filename internal fields are not propagated to
        # Claude — vision API only needs source.{type,media_type,data}.
        assert "storage_path" not in out[0]
        assert "filename" not in out[0]
        # Text block untouched
        assert out[1] == {"type": "text", "text": "What's in this?"}

    def test_unreadable_image_is_skipped(self, service):
        """If storage download returns None (file disappeared, RLS blocked,
        etc.), the image block is dropped so the rest of the message can
        still go through to Claude."""
        with patch(
            "app.services.integrations.supabase.storage_service.download_chat_attachment",
            return_value=None,
        ):
            content = [
                {
                    "type": "image",
                    "storage_path": "p1/c1/missing/screenshot.png",
                    "media_type": "image/png",
                },
                {"type": "text", "text": "fallback question"},
            ]
            out = service._rewrite_image_blocks_for_claude(content)
        # Image block dropped, text preserved
        assert len(out) == 1
        assert out[0] == {"type": "text", "text": "fallback question"}

    def test_multiple_images_all_rewritten(self, service):
        png = b"\x89PNG\r\n\x1a\n" + b"a"
        jpg = b"\xff\xd8\xff" + b"b"

        def fake_download(path):
            if "first" in path:
                return png
            return jpg

        with patch(
            "app.services.integrations.supabase.storage_service.download_chat_attachment",
            side_effect=fake_download,
        ):
            content = [
                {"type": "image", "storage_path": "p/c/first.png", "media_type": "image/png"},
                {"type": "image", "storage_path": "p/c/second.jpg", "media_type": "image/jpeg"},
                {"type": "text", "text": "compare"},
            ]
            out = service._rewrite_image_blocks_for_claude(content)
        assert out[0]["source"]["data"] == base64.standard_b64encode(png).decode("ascii")
        assert out[1]["source"]["data"] == base64.standard_b64encode(jpg).decode("ascii")
        assert out[2] == {"type": "text", "text": "compare"}
