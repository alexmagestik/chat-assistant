"""Клиенты ProxyAPI: OpenAI Responses и Anthropic Messages."""

import json
import socket
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from .errors import ApiError, ApiTimeoutError
from .models import (
    MODE_MESSAGES,
    MODE_RESPONSES,
    is_reasoning_model,
)

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def _build_ssl_context():
    """SSL-контекст с проверкой сертификатов (certifi, если доступен)."""
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


@dataclass
class Reply:
    """Нормализованный ответ модели."""

    text: str
    reasoning: str = ""
    usage: dict = field(default_factory=dict)
    model: str = ""
    mode: str = ""
    reasoning_available: bool = False


class _HttpClient:
    """Общая обвязка для HTTP-запросов с таймаутами и повторами."""

    def __init__(self, config):
        self.config = config
        self.ssl_context = _build_ssl_context()

    def post(self, path, payload, headers):
        url = self.config.base_url + path
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(url, data=body, method="POST")
        request.add_header("Content-Type", "application/json")
        for key, value in headers.items():
            request.add_header(key, value)

        attempts = max(1, self.config.max_retries)
        last_error = None
        for attempt in range(1, attempts + 1):
            try:
                with urllib.request.urlopen(
                    request, timeout=self.config.timeout, context=self.ssl_context
                ) as response:
                    raw = response.read().decode("utf-8")
                return json.loads(raw)
            except urllib.error.HTTPError as exc:
                message = self._parse_http_error(exc)
                if exc.code in _RETRYABLE_STATUS and attempt < attempts:
                    last_error = ApiError(message, status=exc.code)
                    self._backoff(attempt)
                    continue
                raise ApiError(message, status=exc.code) from exc
            except socket.timeout as exc:
                last_error = ApiTimeoutError(
                    f"Превышено время ожидания ({self.config.timeout:g} с)."
                )
                if attempt < attempts:
                    self._backoff(attempt)
                    continue
                raise last_error from exc
            except urllib.error.URLError as exc:
                if isinstance(exc.reason, ssl.SSLError):
                    raise ApiError(
                        "Ошибка TLS при подключении к ProxyAPI: "
                        f"{exc.reason}. Проверьте системные сертификаты."
                    ) from exc
                if isinstance(exc.reason, socket.timeout):
                    last_error = ApiTimeoutError(
                        f"Превышено время ожидания ({self.config.timeout:g} с)."
                    )
                else:
                    last_error = ApiError(f"Сбой сети: {exc.reason}")
                if attempt < attempts:
                    self._backoff(attempt)
                    continue
                raise last_error from exc
            except json.JSONDecodeError as exc:
                raise ApiError("Прокси вернул некорректный JSON.") from exc

        raise last_error or ApiError("Не удалось выполнить запрос.")

    @staticmethod
    def _parse_http_error(exc):
        try:
            raw = exc.read().decode("utf-8")
        except Exception:  # noqa: BLE001 - защита от нечитаемого тела
            raw = ""
        detail = raw.strip()
        try:
            data = json.loads(raw)
            detail = _extract_error_message(data) or detail
        except json.JSONDecodeError:
            pass
        status_text = getattr(exc, "code", "?")
        return detail or f"HTTP {status_text}"

    def _backoff(self, attempt):
        delay = min(2 ** (attempt - 1), 8)
        time.sleep(delay)


def _extract_error_message(data):
    if not isinstance(data, dict):
        return None
    if isinstance(data.get("detail"), str):
        return data["detail"]
    error = data.get("error")
    if isinstance(error, dict) and isinstance(error.get("message"), str):
        return error["message"]
    if isinstance(error, str):
        return error
    if isinstance(data.get("message"), str):
        return data["message"]
    return None


class ResponsesClient(_HttpClient):
    """Клиент формата OpenAI Responses (/v1/responses)."""

    mode = MODE_RESPONSES

    def send(self, messages, model, reasoning=None):
        reasoning = is_reasoning_model(model) if reasoning is None else reasoning
        payload = {
            "model": model,
            "input": [
                {"role": m["role"], "content": m["content"]} for m in messages
            ],
            "max_output_tokens": self.config.max_output_tokens,
        }
        if self.config.system_prompt:
            payload["instructions"] = self.config.system_prompt
        if reasoning:
            payload["reasoning"] = {
                "effort": self.config.reasoning_effort,
                "summary": "auto",
            }

        headers = {"Authorization": f"Bearer {self.config.api_key}"}
        data = self.post("/v1/responses", payload, headers)
        return self._parse(data, model)

    @staticmethod
    def _parse(data, model):
        text_parts = []
        reasoning_parts = []
        for item in data.get("output", []) or []:
            item_type = item.get("type")
            if item_type == "reasoning":
                reasoning_parts.extend(_collect_reasoning_blocks(item))
            elif item_type == "message":
                for block in item.get("content", []) or []:
                    if block.get("type") in {"output_text", "text"}:
                        text_parts.append(block.get("text", ""))

        text = "".join(text_parts).strip()
        if not text and isinstance(data.get("output_text"), str):
            text = data["output_text"].strip()

        return Reply(
            text=text,
            reasoning="\n\n".join(p for p in reasoning_parts if p).strip(),
            reasoning_available=bool(reasoning_parts),
            usage=data.get("usage", {}) or {},
            model=model,
            mode=MODE_RESPONSES,
        )


def _collect_reasoning_blocks(item):
    parts = []
    for block in item.get("summary", []) or []:
        if isinstance(block, dict) and block.get("text"):
            parts.append(block["text"])
    for block in item.get("content", []) or []:
        if isinstance(block, dict) and block.get("text"):
            parts.append(block["text"])
    return parts


class MessagesClient(_HttpClient):
    """Клиент формата Anthropic Messages (/v1/messages)."""

    mode = MODE_MESSAGES

    def send(self, messages, model, reasoning=None):
        reasoning = is_reasoning_model(model) if reasoning is None else reasoning
        max_tokens = self.config.max_output_tokens
        if reasoning:
            max_tokens = max(
                max_tokens, self.config.thinking_budget + 1024
            )

        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": m["role"], "content": m["content"]} for m in messages
            ],
        }
        if self.config.system_prompt:
            payload["system"] = self.config.system_prompt
        if reasoning:
            payload["thinking"] = {
                "type": "enabled",
                "budget_tokens": self.config.thinking_budget,
            }

        headers = {
            "X-API-Key": self.config.api_key,
            "anthropic-version": "2023-06-01",
        }
        data = self.post("/v1/messages", payload, headers)
        return self._parse(data, model)

    @staticmethod
    def _parse(data, model):
        text_parts = []
        reasoning_parts = []
        for block in data.get("content", []) or []:
            block_type = block.get("type")
            if block_type == "text":
                text_parts.append(block.get("text", ""))
            elif block_type == "thinking":
                reasoning_parts.append(block.get("thinking", ""))
            elif block_type == "redacted_thinking":
                reasoning_parts.append("[зашифрованный блок рассуждений]")

        return Reply(
            text="".join(text_parts).strip(),
            reasoning="\n\n".join(p for p in reasoning_parts if p).strip(),
            reasoning_available=bool(reasoning_parts),
            usage=data.get("usage", {}) or {},
            model=model,
            mode=MODE_MESSAGES,
        )


def build_client(mode, config):
    """Возвращает клиент для выбранного режима."""
    if mode == MODE_RESPONSES:
        return ResponsesClient(config)
    if mode == MODE_MESSAGES:
        return MessagesClient(config)
    raise ValueError(f"Неизвестный режим: {mode!r}")
