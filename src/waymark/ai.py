"""Optional local AI helpers for memory structuring."""

from __future__ import annotations

import json
import re
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from waymark.memory import MemoryDraft, fallback_summary, fallback_title, parse_tags

DEFAULT_OLLAMA_ENDPOINT = "http://127.0.0.1:11434"
MAX_MODEL_TAGS = 5
MAX_TAG_LENGTH = 40
MAX_MEMORY_TYPE_LENGTH = 32

MEMORY_STRUCTURE_SYSTEM_PROMPT = """You structure one personal memory.
Return compact JSON only with: title, summary, type, tags.
Do not add facts that are not present in the memory.
Use 2-5 lowercase tags."""


class LocalAiError(RuntimeError):
    """Raised when an optional local AI draft cannot be produced."""


def structure_memory_with_ollama(
    raw_text: str,
    *,
    memory_type: str,
    raw_tags: str,
    model: str,
    endpoint: str = DEFAULT_OLLAMA_ENDPOINT,
    timeout_seconds: float = 30,
) -> MemoryDraft:
    """Ask Ollama for a memory draft and parse it into Waymark's draft shape."""

    response_text = ollama_chat(
        model=model,
        messages=[
            {"role": "system", "content": MEMORY_STRUCTURE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": build_memory_structure_prompt(
                    raw_text,
                    memory_type=memory_type,
                    raw_tags=raw_tags,
                ),
            },
        ],
        endpoint=endpoint,
        timeout_seconds=timeout_seconds,
    )
    return parse_memory_structure_response(
        response_text,
        raw_text=raw_text,
        fallback_memory_type=memory_type,
        raw_tags=raw_tags,
    )


def embed_text_with_ollama(
    text: str,
    *,
    model: str,
    endpoint: str = DEFAULT_OLLAMA_ENDPOINT,
    timeout_seconds: float = 30,
) -> tuple[float, ...]:
    """Ask Ollama for one embedding vector using the current /api/embed endpoint."""

    payload = {
        "model": model,
        "input": text,
    }
    request = Request(
        f"{endpoint.rstrip('/')}/api/embed",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        response: Any = urlopen(request, timeout=timeout_seconds)
        with response:
            body = cast(bytes, response.read())
    except HTTPError as error:
        raise LocalAiError(f"Ollama returned HTTP {error.code}.") from error
    except URLError as error:
        raise LocalAiError(f"Ollama is not reachable: {error.reason}.") from error
    except TimeoutError as error:
        raise LocalAiError("Ollama request timed out.") from error
    except OSError as error:
        raise LocalAiError(str(error)) from error

    return parse_ollama_embed_response(body)


def parse_ollama_embed_response(body: bytes) -> tuple[float, ...]:
    try:
        data = json.loads(body.decode("utf-8"))
        embeddings = data["embeddings"]
    except (KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise LocalAiError("Ollama returned an unexpected embedding response shape.") from error

    if (
        not isinstance(embeddings, list)
        or not embeddings
        or not isinstance(embeddings[0], list)
        or not embeddings[0]
    ):
        raise LocalAiError("Ollama returned an empty embedding vector.")

    try:
        return tuple(float(value) for value in embeddings[0])
    except (TypeError, ValueError) as error:
        raise LocalAiError("Ollama returned a non-numeric embedding vector.") from error


def build_memory_structure_prompt(raw_text: str, *, memory_type: str, raw_tags: str) -> str:
    return (
        "Draft a memory card for this saved memory.\n"
        f"Requested type: {memory_type.strip() or 'daily'}\n"
        f"User tags: {raw_tags.strip() or 'none'}\n\n"
        "Memory:\n"
        f"{raw_text.strip()}"
    )


def ollama_chat(
    *,
    model: str,
    messages: list[dict[str, str]],
    endpoint: str = DEFAULT_OLLAMA_ENDPOINT,
    timeout_seconds: float = 30,
) -> str:
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "format": "json",
    }
    request = Request(
        f"{endpoint.rstrip('/')}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        response: Any = urlopen(request, timeout=timeout_seconds)
        with response:
            body = cast(bytes, response.read())
    except HTTPError as error:
        raise LocalAiError(f"Ollama returned HTTP {error.code}.") from error
    except URLError as error:
        raise LocalAiError(f"Ollama is not reachable: {error.reason}.") from error
    except TimeoutError as error:
        raise LocalAiError("Ollama request timed out.") from error
    except OSError as error:
        raise LocalAiError(str(error)) from error

    try:
        data = json.loads(body.decode("utf-8"))
        content = data["message"]["content"]
    except (KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise LocalAiError("Ollama returned an unexpected response shape.") from error

    if not isinstance(content, str) or not content.strip():
        raise LocalAiError("Ollama returned an empty memory draft.")
    return content


def parse_memory_structure_response(
    response_text: str,
    *,
    raw_text: str,
    fallback_memory_type: str,
    raw_tags: str = "",
) -> MemoryDraft:
    data = parse_json_object(response_text)
    clean_text = raw_text.strip()
    fallback_type = normalize_memory_type(fallback_memory_type)
    clean_type = normalize_memory_type(
        data.get("type") or data.get("memory_type"),
        fallback=fallback_type,
    )
    model_tags = normalize_model_tags(data.get("tags"))
    tags = tuple(sorted(set(parse_tags(raw_tags)) | set(model_tags)))

    return MemoryDraft(
        raw_text=clean_text,
        memory_type=clean_type,
        title=clean_text_field(data.get("title"), fallback=fallback_title(clean_text), limit=72),
        summary=clean_text_field(
            data.get("summary"),
            fallback=fallback_summary(clean_text),
            limit=240,
        ),
        tags=tags,
    )


def parse_json_object(response_text: str) -> dict[str, Any]:
    stripped = response_text.strip()
    if stripped.startswith("```"):
        stripped = strip_code_fence(stripped)

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise LocalAiError("Local AI did not return a JSON object.")

    payload = stripped[start : end + 1]
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as error:
        repaired_payload = repair_json_payload(payload)
        try:
            data = json.loads(repaired_payload)
        except json.JSONDecodeError:
            raise LocalAiError("Local AI returned invalid JSON.") from error
    if not isinstance(data, dict):
        raise LocalAiError("Local AI did not return a JSON object.")
    return cast(dict[str, Any], data)


def strip_code_fence(text: str) -> str:
    lines = text.splitlines()
    if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return text


def normalize_model_tags(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        tags = parse_tags(value)
        return clean_model_tags(tags)
    if isinstance(value, list):
        tags = parse_tags(",".join(str(item) for item in value if str(item).strip()))
        return clean_model_tags(tags)
    return ()


def clean_model_tags(tags: tuple[str, ...]) -> tuple[str, ...]:
    clean_tags = tuple(
        normalized
        for tag in tags
        if (normalized := normalize_slug(tag, max_length=MAX_TAG_LENGTH))
    )
    return clean_tags[:MAX_MODEL_TAGS]


def normalize_memory_type(value: object, *, fallback: str = "daily") -> str:
    normalized = normalize_slug(value, max_length=MAX_MEMORY_TYPE_LENGTH)
    if normalized:
        return normalized
    fallback_type = normalize_slug(fallback, max_length=MAX_MEMORY_TYPE_LENGTH)
    return fallback_type or "daily"


def normalize_slug(value: object, *, max_length: int) -> str:
    if not isinstance(value, str):
        return ""
    lowered = value.strip().lower()
    if not lowered:
        return ""
    normalized = re.sub(r"[^a-z0-9_-]+", "-", lowered)
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-_")
    if len(normalized) <= max_length:
        return normalized
    return normalized[:max_length].rstrip("-_")


def repair_json_payload(payload: str) -> str:
    return re.sub(r",\s*([}\]])", r"\1", payload)


def clean_text_field(value: object, *, fallback: str, limit: int) -> str:
    if isinstance(value, str):
        text = " ".join(value.strip().split())
    else:
        text = ""
    if not text:
        text = fallback
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3].rstrip()}..."
