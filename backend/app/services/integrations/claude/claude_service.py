"""
Claude Service - Wrapper for Claude API interactions.

Educational Note: This service provides a clean interface to the Claude API.
It's designed to be used by multiple callers (chat, subagents, tools, etc.)
with different configurations (prompts, tools, temperature).

Key Design Decisions:
- Stateless: Each call is independent, caller provides all context
- Flexible: Accepts variable parameters for different use cases
- Reusable: Can be called from main chat, subagents, RAG pipeline, etc.
"""
import contextvars
import logging
import os
import threading
import time
from typing import Optional, List, Dict, Any, Callable
import anthropic
from anthropic import APIStatusError, APITimeoutError, APIConnectionError

from app.utils.cost_tracking import add_usage as add_cost_usage, check_user_spending_limit

logger = logging.getLogger(__name__)

# Retryable HTTP status codes
_RATE_LIMIT_CODES = (429, 529)  # rate limit + overloaded
_SERVER_ERROR_CODES = (500, 502, 503)
_MAX_RETRIES = 3

# ContextVar carrying the signed-in user's email for the current logical
# call. Routes that dispatch Claude calls into worker threads (e.g. the
# SSE chat endpoint) lose Flask's request context at the thread boundary,
# so `get_request_identity()` returns the unauthenticated sentinel inside
# the worker. Those callers should set this var at the worker's entry
# point via `set_current_user_email(...)` before invoking any Claude API.
# `_resolve_user_email` consults it as a fallback when the request-context
# lookup yields nothing. ContextVar (not threading.local) so we stay
# forwards-compatible with an asyncio migration.
_current_user_email: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "noobbook_current_user_email", default=None
)


def set_current_user_email(email: Optional[str]) -> None:
    """Stash the current user's email for the active execution context so
    Claude calls running outside a Flask request context (worker threads,
    background tasks) can still tag Opik traces with it.

    Idempotent and safe to call with None (clears the value). Per-thread
    scoping: setting in one thread does not leak to other threads."""
    _current_user_email.set(email)


class ClaudeService:
    """
    Service class for Claude API interactions.

    Educational Note: This is a thin wrapper around the Anthropic client.
    It handles client initialization and provides a consistent interface
    for making API calls with various configurations.
    """

    def __init__(self):
        """Initialize the Claude service."""
        self._client: Optional[anthropic.Anthropic] = None
        self._opik_enabled: bool = False

    def _get_client(self) -> anthropic.Anthropic:
        """
        Get or create the Anthropic client.

        Educational Note: Lazy initialization to avoid errors if API key
        is not set at import time.

        Raises:
            ValueError: If ANTHROPIC_API_KEY is not set
        """
        if self._client is None:
            api_key = os.getenv('ANTHROPIC_API_KEY')
            if not api_key:
                logger.error("ANTHROPIC_API_KEY not found in environment")
                raise ValueError("ANTHROPIC_API_KEY not found in environment")

            client = anthropic.Anthropic(api_key=api_key)

            # Wrap with Opik observability if configured
            # Educational Note: track_anthropic() is a transparent wrapper that
            # auto-logs every API call (prompt, response, tokens, latency, cost)
            # to the Opik dashboard. If OPIK_API_KEY is not set, we skip entirely.
            opik_api_key = os.getenv('OPIK_API_KEY')
            if opik_api_key:
                try:
                    import opik
                    from opik.integrations.anthropic import track_anthropic

                    opik_url = os.getenv('OPIK_URL_OVERRIDE')
                    opik_workspace = os.getenv('OPIK_WORKSPACE')
                    opik_project = os.getenv('OPIK_PROJECT_NAME', 'NoobBook')

                    configure_kwargs = {"api_key": opik_api_key}
                    if opik_workspace:
                        configure_kwargs["workspace"] = opik_workspace
                    if opik_url:
                        configure_kwargs["url_override"] = opik_url

                    opik.configure(**configure_kwargs)
                    client = track_anthropic(client, project_name=opik_project)
                    self._opik_enabled = True
                    logger.info("Opik observability enabled (project: %s)", opik_project)
                except ImportError:
                    logger.warning("OPIK_API_KEY set but 'opik' package not installed. Skipping.")
                except Exception as e:
                    logger.warning("Failed to init Opik: %s. Continuing without observability.", e)

            self._client = client
        return self._client

    def _call_with_retry(self, api_fn: Callable, max_retries: int = _MAX_RETRIES):
        """
        Retry transient Claude API errors with exponential backoff.

        Educational Note: The Claude API can return transient errors:
        - 429 (rate limit) / 529 (overloaded) → wait 30s per attempt
        - 500/502/503 (server error) → wait 2^attempt * 2 seconds
        - Timeout / connection errors → same short backoff

        Non-retryable errors (400, 401, 403, 413) raise immediately.
        This is called centrally so all callers — chat, agents,
        extraction, studio — get retries for free.
        """
        for attempt in range(max_retries + 1):
            try:
                return api_fn()
            except (APITimeoutError, APIConnectionError) as e:
                if attempt >= max_retries:
                    raise
                wait = (2 ** attempt) * 2
                logger.warning(
                    "CLAUDE_RETRY attempt=%d/%d reason=%s wait_ms=%d detail=%s",
                    attempt + 1, max_retries, type(e).__name__, wait * 1000, e,
                )
                time.sleep(wait)
            except APIStatusError as e:
                status = e.status_code
                if status in _RATE_LIMIT_CODES:
                    if attempt >= max_retries:
                        raise
                    wait = (attempt + 1) * 30
                    logger.warning(
                        "CLAUDE_RETRY attempt=%d/%d reason=rate_limit_%d wait_ms=%d",
                        attempt + 1, max_retries, status, wait * 1000,
                    )
                    time.sleep(wait)
                elif status in _SERVER_ERROR_CODES:
                    if attempt >= max_retries:
                        raise
                    wait = (2 ** attempt) * 2
                    logger.warning(
                        "CLAUDE_RETRY attempt=%d/%d reason=server_%d wait_ms=%d",
                        attempt + 1, max_retries, status, wait * 1000,
                    )
                    time.sleep(wait)
                else:
                    raise  # 400, 401, 403, 413 — don't retry

    def _build_opik_kwargs(
        self,
        project_id: Optional[str] = None,
        user_id: Optional[str] = None,
        user_email: Optional[str] = None,
        chat_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Build the kwargs dict for update_current_trace()."""
        kwargs: Dict[str, Any] = {}
        metadata = {}
        if project_id:
            metadata["project_id"] = project_id
        if user_id:
            metadata["user_id"] = user_id
        if user_email:
            # Stand-in for a backend audit log: lets us answer "which user
            # made this call?" from the Opik dashboard until the real audit
            # log table ships.
            metadata["user_email"] = user_email
        if metadata:
            kwargs["metadata"] = metadata
        if chat_id:
            kwargs["thread_id"] = chat_id
        if tags:
            kwargs["tags"] = tags
        return kwargs

    @staticmethod
    def _resolve_user_email(user_email: Optional[str]) -> Optional[str]:
        """Auto-fill user_email when caller didn't pass one explicitly.

        Resolution order:
          1. Explicit kwarg from the caller (highest priority).
          2. Flask request context — `get_request_identity().email`.
             Works when Claude is called directly from a route handler.
          3. ContextVar `_current_user_email` — set by route workers
             that dispatch Claude calls into a thread without a Flask
             request context (e.g. SSE chat streaming).

        Falls through to None if none of those yield a value. Best-effort
        throughout; any exception in the lookup chain returns None rather
        than failing the Claude call."""
        if user_email is not None:
            return user_email
        try:
            from app.services.auth.rbac import get_request_identity
            ident = get_request_identity()
            if ident.is_authenticated and ident.email:
                return ident.email
        except Exception:
            pass
        try:
            return _current_user_email.get()
        except Exception:
            return None

    def _run_tracked(
        self,
        fn,
        *,
        opik_kwargs: Dict[str, Any],
        trace_input: Optional[Dict[str, Any]] = None,
        trace_name: str = "noobbook_llm_call",
    ):
        """
        Run fn() inside an @opik.track() parent trace with metadata.

        Educational Note: track_anthropic() auto-creates a child span for
        every client.messages.create() call, but that span is finalized before
        we can attach metadata. @opik.track() creates a parent trace around the
        call. update_current_trace() injects user_id, project_id, chat_id
        (as thread_id), and tags into that parent. The child span nests inside.

        Opik uses background batching by default (flush=False), so the trace
        upload adds <5ms overhead — it never blocks the API response.

        API errors from fn() always propagate to the caller — only Opik
        setup errors are caught and ignored.
        """
        if not self._opik_enabled or not opik_kwargs:
            return fn()

        try:
            import opik
            from opik.opik_context import update_current_trace
        except ImportError:
            return fn()

        @opik.track(name=trace_name)
        def tracked():
            try:
                if trace_input:
                    opik_kwargs["input"] = trace_input
                update_current_trace(**opik_kwargs)
            except Exception:
                pass  # Never fail on metadata injection
            return fn()  # API errors propagate normally

        return tracked()  # API errors propagate to caller

    def send_message(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 4096,
        temperature: float = 0.0,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Dict[str, Any]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
        project_id: Optional[str] = None,
        user_id: Optional[str] = None,
        user_email: Optional[str] = None,
        chat_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        enable_prompt_cache: bool = False,
    ) -> Dict[str, Any]:
        """
        Send messages to Claude and get a response.

        Educational Note: This is the core method for Claude API interaction.
        Different callers can customize behavior via parameters:
        - Main chat: Just messages + system prompt
        - Subagents: Messages + tools + specific prompts
        - RAG: Messages with context + retrieval tools

        Args:
            messages: List of message dicts with 'role' and 'content'
            system_prompt: Optional system prompt for this conversation
            model: Claude model to use (default: claude-sonnet-4-6)
            max_tokens: Maximum tokens in response (default: 4096)
            temperature: Sampling temperature (default: 0.2)
            tools: Optional list of tool definitions for tool use
            tool_choice: Optional tool choice configuration
            extra_headers: Optional headers for beta features (e.g., {"anthropic-beta": "web-fetch-2025-09-10"})
            project_id: Optional project ID for cost tracking (if provided, costs are tracked)

        Returns:
            Dict containing:
                - content: The response content (text or tool_use blocks)
                - model: Model used
                - usage: Token usage stats
                - stop_reason: Why the response ended
                - raw_response: Full API response for advanced use cases

        Raises:
            ValueError: If API key is not configured
            anthropic.APIError: If API call fails
        """
        # Check spending limit before making the API call
        limit_error = check_user_spending_limit(user_id)
        if limit_error:
            raise ValueError(limit_error)

        client = self._get_client()
        api_params = self._build_api_params(
            messages=messages,
            system_prompt=system_prompt,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            tools=tools,
            tool_choice=tool_choice,
            extra_headers=extra_headers,
            enable_prompt_cache=enable_prompt_cache,
        )

        # Make API call (wrapped in Opik parent trace with metadata if enabled)
        user_email = self._resolve_user_email(user_email)
        opik_kwargs = self._build_opik_kwargs(
            project_id=project_id,
            user_id=user_id,
            user_email=user_email,
            chat_id=chat_id,
            tags=tags,
        )
        # Show the last user message as trace input for quick scanning in the dashboard
        last_user_msg = next(
            (m.get("content", "") for m in reversed(messages) if m.get("role") == "user"),
            "",
        )
        # Truncate for trace name (Opik dashboard column); full text in trace_input
        short_name = (last_user_msg[:80] + "...") if isinstance(last_user_msg, str) and len(last_user_msg) > 80 else last_user_msg
        trace_name = str(short_name) if short_name else "noobbook_llm_call"
        trace_input = {"prompt": last_user_msg, "model": model, "message_count": len(messages)}
        call_t0 = time.monotonic()
        response = self._run_tracked(
            lambda: self._call_with_retry(lambda: client.messages.create(**api_params)),
            opik_kwargs=opik_kwargs,
            trace_input=trace_input,
            trace_name=trace_name,
        )

        # Cache fields are only populated when prompt caching is in play;
        # default to 0 so non-cached calls behave exactly as before.
        cache_creation_tokens = getattr(response.usage, "cache_creation_input_tokens", 0) or 0
        cache_read_tokens = getattr(response.usage, "cache_read_input_tokens", 0) or 0

        # Single success line per Claude call so a customer turn reads as a
        # contiguous story in the bundle. Opik already captures these fields
        # but backend.log is what we ship in support bundles. Counts only —
        # we never log the prompt or response body here.
        logger.info(
            "CLAUDE_CALL model=%s ms=%d in_tok=%d out_tok=%d cache_read=%d cache_create=%d stop=%s",
            response.model,
            int((time.monotonic() - call_t0) * 1000),
            response.usage.input_tokens,
            response.usage.output_tokens,
            cache_read_tokens,
            cache_creation_tokens,
            response.stop_reason,
        )

        # Track costs if project_id provided (also per-chat if chat_id set)
        if project_id:
            add_cost_usage(
                project_id=project_id,
                model=response.model,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                user_id=user_id,
                chat_id=chat_id,
                cache_creation_tokens=cache_creation_tokens,
                cache_read_tokens=cache_read_tokens,
            )

        # Return raw response data - all parsing happens in claude_parsing_utils
        return {
            "content_blocks": response.content,  # Raw Anthropic content blocks
            "model": response.model,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "cache_creation_input_tokens": cache_creation_tokens,
                "cache_read_input_tokens": cache_read_tokens,
            },
            "stop_reason": response.stop_reason,
        }

    def stream_message(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 4096,
        temperature: float = 0.0,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Dict[str, Any]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
        project_id: Optional[str] = None,
        on_text_delta: Optional[Callable[[str], None]] = None,
        user_id: Optional[str] = None,
        user_email: Optional[str] = None,
        chat_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        enable_prompt_cache: bool = False,
    ) -> Dict[str, Any]:
        """
        Stream a Claude response and forward text deltas through a callback.

        Educational Note: This uses Anthropic's streaming API so callers can
        surface partial assistant text in real time while still receiving a
        final response object compatible with send_message().
        """
        # Check spending limit before making the API call
        limit_error = check_user_spending_limit(user_id)
        if limit_error:
            raise ValueError(limit_error)

        client = self._get_client()
        api_params = self._build_api_params(
            messages=messages,
            system_prompt=system_prompt,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            tools=tools,
            tool_choice=tool_choice,
            extra_headers=extra_headers,
            enable_prompt_cache=enable_prompt_cache,
        )

        # Wrap streaming in Opik parent trace with metadata + retry
        def _do_stream():
            def _stream_once():
                with client.messages.stream(**api_params) as stream:
                    for delta in stream.text_stream:
                        if on_text_delta:
                            on_text_delta(delta)
                    return stream.get_final_message()
            return self._call_with_retry(_stream_once)

        user_email = self._resolve_user_email(user_email)
        opik_kwargs = self._build_opik_kwargs(
            project_id=project_id,
            user_id=user_id,
            user_email=user_email,
            chat_id=chat_id,
            tags=tags,
        )
        last_user_msg = next(
            (m.get("content", "") for m in reversed(messages) if m.get("role") == "user"),
            "",
        )
        short_name = (last_user_msg[:80] + "...") if isinstance(last_user_msg, str) and len(last_user_msg) > 80 else last_user_msg
        trace_name = str(short_name) if short_name else "noobbook_llm_call"
        trace_input = {"prompt": last_user_msg, "model": model, "message_count": len(messages)}
        # Pair of start/done lines (one per stream, NOT per delta) — the
        # interesting failure mode is "stream went away mid-response", so a
        # missing _DONE matched to a _START tells the story.
        logger.info(
            "CLAUDE_STREAM_START model=%s msg_count=%d", model, len(messages)
        )
        call_t0 = time.monotonic()
        response = self._run_tracked(_do_stream, opik_kwargs=opik_kwargs, trace_input=trace_input, trace_name=trace_name)

        cache_creation_tokens = getattr(response.usage, "cache_creation_input_tokens", 0) or 0
        cache_read_tokens = getattr(response.usage, "cache_read_input_tokens", 0) or 0

        logger.info(
            "CLAUDE_STREAM_DONE model=%s ms=%d in_tok=%d out_tok=%d cache_read=%d cache_create=%d stop=%s",
            response.model,
            int((time.monotonic() - call_t0) * 1000),
            response.usage.input_tokens,
            response.usage.output_tokens,
            cache_read_tokens,
            cache_creation_tokens,
            response.stop_reason,
        )

        if project_id:
            add_cost_usage(
                project_id=project_id,
                model=response.model,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                user_id=user_id,
                chat_id=chat_id,
                cache_creation_tokens=cache_creation_tokens,
                cache_read_tokens=cache_read_tokens,
            )

        return {
            "content_blocks": response.content,
            "model": response.model,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "cache_creation_input_tokens": cache_creation_tokens,
                "cache_read_input_tokens": cache_read_tokens,
            },
            "stop_reason": response.stop_reason,
        }

    def _build_api_params(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: Optional[str],
        model: str,
        max_tokens: int,
        temperature: float,
        tools: Optional[List[Dict[str, Any]]],
        tool_choice: Optional[Dict[str, Any]],
        extra_headers: Optional[Dict[str, str]],
        enable_prompt_cache: bool = False,
    ) -> Dict[str, Any]:
        """Build the shared Anthropic request payload.

        When `enable_prompt_cache` is True, the system prompt is converted to
        the structured block form and a `cache_control: {type: "ephemeral"}`
        breakpoint is attached to it and to the last tool definition. This
        opts the caller into Anthropic prompt caching, which bills subsequent
        cache hits at 0.1× the normal input rate.

        Note: Anthropic silently ignores cache_control on blocks below the
        per-model minimum (~1024 tokens for Sonnet/Opus, ~2048 for Haiku).
        Sub-minimum blocks are still served — just not cached — so this is
        safe to enable broadly for the chat hot path.
        """
        # Build API call parameters
        api_params = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": (
                _messages_with_cache_breakpoint(messages)
                if enable_prompt_cache
                else messages
            ),
        }

        # Add optional parameters only if provided
        if system_prompt:
            api_params["system"] = (
                _system_block_with_cache(system_prompt)
                if enable_prompt_cache
                else system_prompt
            )

        # Opus 4.7 dropped all sampling controls (`temperature`, `top_p`,
        # `top_k`) — the API returns 400 ("`temperature` is deprecated for
        # this model.") on any of them. We don't currently pass `top_p`/
        # `top_k` anywhere, but `temperature` flows in from prompt configs,
        # so strip it for the 4.7 family. Every other model keeps the prior
        # "only emit if non-default" behaviour.
        if not model.startswith("claude-opus-4-7") and temperature != 0.2:
            api_params["temperature"] = temperature

        if tools:
            api_params["tools"] = (
                _tools_with_cache_breakpoint(tools) if enable_prompt_cache else tools
            )

        if tool_choice:
            api_params["tool_choice"] = tool_choice

        # Prompt-caching of the messages array is now handled by
        # `_messages_with_cache_breakpoint()` above — it attaches a
        # cache_control breakpoint to the last content block of the
        # last message. A previous draft passed `cache_control` as a
        # TOP-LEVEL kwarg here, which Anthropic's SDK rejects with
        # `Messages.create() got an unexpected keyword argument
        # 'cache_control'` on every released version. The per-block
        # breakpoint pattern is the canonical Anthropic prompt-caching
        # API and works on every SDK version since caching launched.

        # Add extra headers for beta features (e.g., web_fetch)
        if extra_headers:
            api_params["extra_headers"] = extra_headers

        return api_params

    def count_tokens(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        model: str = "claude-sonnet-4-6",
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> int:
        """
        Count input tokens for a given set of messages without making an API call.

        Educational Note: This is useful for determining context size before:
        - Deciding whether to use RAG vs full context
        - Estimating costs
        - Checking if content fits within model limits

        Args:
            messages: List of message dicts with 'role' and 'content'
            system_prompt: Optional system prompt to include in count
            model: Claude model to use for tokenization
            tools: Optional list of tool definitions (tools also consume tokens)

        Returns:
            Number of input tokens
        """
        client = self._get_client()

        # Build API call parameters
        api_params = {
            "model": model,
            "messages": messages,
        }

        # Add optional parameters
        if system_prompt:
            api_params["system"] = system_prompt

        if tools:
            api_params["tools"] = tools

        # Call the count_tokens API
        response = client.messages.count_tokens(**api_params)

        return response.input_tokens


def _system_block_with_cache(system_prompt: str) -> List[Dict[str, Any]]:
    """
    Convert a plain string system prompt into Anthropic's structured-block
    form with a cache_control breakpoint on it.

    The Anthropic API accepts either form — `system="..."` or
    `system=[{"type":"text", "text":"...", "cache_control":{...}}]` — and
    cache_control only attaches to the block form.

    Note: Anthropic enforces a minimum cacheable size (~1024 tokens for
    Sonnet/Opus, ~2048 for Haiku). Smaller blocks are silently served
    uncached — no error, no discount — so this helper is safe to apply
    even to short prompts. See:
    https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching
    """
    return [
        {
            "type": "text",
            "text": system_prompt,
            "cache_control": {"type": "ephemeral"},
        }
    ]


def _messages_with_cache_breakpoint(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Return a shallow-copy messages list with a `cache_control: ephemeral`
    breakpoint on the last content block of the last message.

    Anthropic prompt caching attaches breakpoints to individual content
    blocks, not to the top-level request. Marking the last block of the
    last message caches the entire prefix (system + tools + every prior
    message) up to and including that point. As the conversation/loop
    grows, callers rebuild this list each turn so the breakpoint slides
    forward naturally — no sticky cache_control left on now-historical
    blocks.

    Plain-string content is converted to block form so the cache_control
    field has somewhere to attach. Empty / unrecognised content shapes
    are returned unmodified — caching is best-effort.
    """
    if not messages:
        return messages

    cached = list(messages)
    last_msg = dict(cached[-1])
    content = last_msg.get("content")

    if isinstance(content, str):
        last_msg["content"] = [
            {"type": "text", "text": content, "cache_control": {"type": "ephemeral"}}
        ]
    elif isinstance(content, list) and content:
        new_content = list(content)
        new_content[-1] = {**new_content[-1], "cache_control": {"type": "ephemeral"}}
        last_msg["content"] = new_content
    else:
        return messages  # nothing to attach to — best-effort skip

    cached[-1] = last_msg
    return cached


def _tools_with_cache_breakpoint(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Return a shallow-copy tools list with a cache_control breakpoint on the
    last tool. The breakpoint covers every block up to and including itself,
    so marking the last tool caches the entire tools array.

    We never mutate the caller's tool dicts in place — chat builds the tools
    list each turn from registries, and a sticky cache_control field would
    leak into agents that share the same tool definitions but don't opt into
    caching.
    """
    if not tools:
        return tools
    cached = list(tools)
    cached[-1] = {**cached[-1], "cache_control": {"type": "ephemeral"}}
    return cached


# Singleton instance for easy import
claude_service = ClaudeService()


# In-process dedupe so repeat sends in the same chat session don't keep
# re-issuing the same tag update against Opik. Bounded by chat count
# in this process — fine for our scale.
_tagged_threads: set = set()
_tagged_threads_lock = threading.Lock()


def tag_chat_thread(
    chat_id: Optional[str],
    user_email: Optional[str],
    project_id: Optional[str] = None,
) -> None:
    """Tag the Opik thread for this chat with user identity so the thread
    list is filterable by user without drilling into each trace.

    Why a separate call: Opik's `update_thread` REST API supports tags but
    not arbitrary metadata. `update_current_trace(metadata=...)` only writes
    to the trace, not the parent thread record. This bridges that gap.

    Fire-and-forget: spawns a daemon thread that sleeps briefly (waiting for
    the Opik trace batch to flush so the thread record exists upstream),
    then calls `update_thread` with `tags_to_add`. Never raises into the
    caller. Deduped per (chat_id, user_email) per process — tag operations
    are idempotent on Opik's side, but skipping the network round trip when
    we've already done it is free."""
    if not chat_id or not user_email:
        return
    key = (chat_id, user_email)
    with _tagged_threads_lock:
        if key in _tagged_threads:
            return
        _tagged_threads.add(key)

    def _run() -> None:
        try:
            # Opik's trace uploader batches with a ~5s default window. The
            # thread record is created server-side when the first trace
            # carrying that thread_id is ingested, so we wait long enough
            # to cover the worst-case batch flush plus a little slack.
            time.sleep(8)
            import opik

            client = opik.Opik()
            project_name = os.getenv("OPIK_PROJECT_NAME", "NoobBook")
            threads = client.search_threads(
                project_name=project_name,
                filter_string=f'id = "{chat_id}"',
                max_results=1,
            )
            if not threads:
                # Trace flush hasn't happened yet — un-dedupe so the next
                # message in this chat retries. Avoids permanently giving
                # up because of a timing race.
                with _tagged_threads_lock:
                    _tagged_threads.discard(key)
                return
            thread_model_id = getattr(threads[0], "thread_model_id", None)
            if not thread_model_id:
                return
            tags = [f"user:{user_email}"]
            if project_id:
                tags.append(f"project:{project_id}")
            client.rest_client.traces.update_thread(
                thread_model_id=thread_model_id,
                tags_to_add=tags,
            )
        except Exception as exc:
            # Never let observability tagging break a chat. Un-dedupe so a
            # transient Opik outage doesn't permanently swallow tagging for
            # this chat.
            logger.debug("Opik thread tag failed (chat=%s): %s", chat_id, exc)
            with _tagged_threads_lock:
                _tagged_threads.discard(key)

    threading.Thread(target=_run, daemon=True, name=f"opik-tag-{chat_id[:8]}").start()
