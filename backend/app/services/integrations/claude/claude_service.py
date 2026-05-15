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
import logging
import os
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
                    "API timeout/connection error (attempt %d/%d), retrying in %ds: %s",
                    attempt + 1, max_retries, wait, e,
                )
                time.sleep(wait)
            except APIStatusError as e:
                status = e.status_code
                if status in _RATE_LIMIT_CODES:
                    if attempt >= max_retries:
                        raise
                    wait = (attempt + 1) * 30
                    logger.warning(
                        "Rate limit/overloaded %d (attempt %d/%d), retrying in %ds",
                        status, attempt + 1, max_retries, wait,
                    )
                    time.sleep(wait)
                elif status in _SERVER_ERROR_CODES:
                    if attempt >= max_retries:
                        raise
                    wait = (2 ** attempt) * 2
                    logger.warning(
                        "Server error %d (attempt %d/%d), retrying in %ds",
                        status, attempt + 1, max_retries, wait,
                    )
                    time.sleep(wait)
                else:
                    raise  # 400, 401, 403, 413 — don't retry

    def _build_opik_kwargs(
        self,
        project_id: Optional[str] = None,
        user_id: Optional[str] = None,
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
        if metadata:
            kwargs["metadata"] = metadata
        if chat_id:
            kwargs["thread_id"] = chat_id
        if tags:
            kwargs["tags"] = tags
        return kwargs

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
        opik_kwargs = self._build_opik_kwargs(project_id=project_id, user_id=user_id, chat_id=chat_id, tags=tags)
        # Show the last user message as trace input for quick scanning in the dashboard
        last_user_msg = next(
            (m.get("content", "") for m in reversed(messages) if m.get("role") == "user"),
            "",
        )
        # Truncate for trace name (Opik dashboard column); full text in trace_input
        short_name = (last_user_msg[:80] + "...") if isinstance(last_user_msg, str) and len(last_user_msg) > 80 else last_user_msg
        trace_name = str(short_name) if short_name else "noobbook_llm_call"
        trace_input = {"prompt": last_user_msg, "model": model, "message_count": len(messages)}
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

        opik_kwargs = self._build_opik_kwargs(project_id=project_id, user_id=user_id, chat_id=chat_id, tags=tags)
        last_user_msg = next(
            (m.get("content", "") for m in reversed(messages) if m.get("role") == "user"),
            "",
        )
        short_name = (last_user_msg[:80] + "...") if isinstance(last_user_msg, str) and len(last_user_msg) > 80 else last_user_msg
        trace_name = str(short_name) if short_name else "noobbook_llm_call"
        trace_input = {"prompt": last_user_msg, "model": model, "message_count": len(messages)}
        response = self._run_tracked(_do_stream, opik_kwargs=opik_kwargs, trace_input=trace_input, trace_name=trace_name)

        cache_creation_tokens = getattr(response.usage, "cache_creation_input_tokens", 0) or 0
        cache_read_tokens = getattr(response.usage, "cache_read_input_tokens", 0) or 0

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
            "messages": messages,
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

        # Automatic prompt caching for the messages array. Setting
        # `cache_control` at the top level tells Anthropic to place a cache
        # breakpoint on the last cacheable block of `messages` and slide
        # that breakpoint forward as the conversation/loop grows — so each
        # turn after the first reads the prior turns from cache instead of
        # paying full input price. Stacks with the explicit breakpoints on
        # `system` and the last tool above; budget goes 2-of-4 → 3-of-4.
        # 5-min TTL (default ephemeral) is enough for chat sessions and
        # in-flight agentic loops; 1h would double write cost for no win.
        if enable_prompt_cache:
            api_params["cache_control"] = {"type": "ephemeral"}

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
