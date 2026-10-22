"""Загрузка и валидация конфигурации из .env."""

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

from .errors import ConfigurationError
from .models import (
    DEFAULT_MESSAGES_MODEL,
    DEFAULT_RESPONSES_MODEL,
    MODE_MESSAGES,
    MODE_RESPONSES,
    MODES,
)


@dataclass
class Config:
    """Все настройки ассистента, собранные из переменных окружения."""

    api_key: str
    base_url: str = "https://api.proxyapi.ru"
    timeout: float = 120.0
    max_retries: int = 3
    default_mode: str = MODE_RESPONSES
    responses_model: str = DEFAULT_RESPONSES_MODEL
    messages_model: str = DEFAULT_MESSAGES_MODEL
    system_prompt: str = ""
    max_output_tokens: int = 4096
    reasoning_effort: str = "medium"
    thinking_budget: int = 2048
    history_file: str = ".assistant_history.json"
    model_overrides: dict = field(default_factory=dict)

    def model_for_mode(self, mode):
        return self.responses_model if mode == MODE_RESPONSES else self.messages_model


def _get_float(name, default):
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} должно быть числом, получено: {raw!r}") from exc


def _get_int(name, default):
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} должно быть целым числом, получено: {raw!r}") from exc


def load_config():
    """Читает .env и возвращает валидный объект Config."""
    load_dotenv()

    api_key = os.getenv("PROXY_API_KEY", "").strip()
    if not api_key:
        raise ConfigurationError(
            "Не задан PROXY_API_KEY. Добавьте ключ в файл .env."
        )

    default_mode = os.getenv("DEFAULT_MODE", MODE_RESPONSES).strip().lower()
    if default_mode not in MODES:
        raise ConfigurationError(
            f"DEFAULT_MODE должен быть одним из {MODES}, получено: {default_mode!r}"
        )

    max_output_tokens = _get_int("MAX_OUTPUT_TOKENS", 4096)
    if max_output_tokens <= 0:
        raise ConfigurationError("MAX_OUTPUT_TOKENS должен быть больше нуля.")

    thinking_budget = _get_int("THINKING_BUDGET", 2048)
    if thinking_budget <= 0:
        raise ConfigurationError("THINKING_BUDGET должен быть больше нуля.")

    effort = os.getenv("REASONING_EFFORT", "medium").strip().lower()
    if effort not in {"minimal", "low", "medium", "high"}:
        raise ConfigurationError(
            "REASONING_EFFORT должен быть minimal/low/medium/high, "
            f"получено: {effort!r}"
        )

    return Config(
        api_key=api_key,
        base_url=os.getenv("PROXY_API_BASE", "https://api.proxyapi.ru").rstrip("/"),
        timeout=_get_float("REQUEST_TIMEOUT", 120.0),
        max_retries=_get_int("MAX_RETRIES", 3),
        default_mode=default_mode,
        responses_model=os.getenv("RESPONSES_MODEL", DEFAULT_RESPONSES_MODEL).strip(),
        messages_model=os.getenv("MESSAGES_MODEL", DEFAULT_MESSAGES_MODEL).strip(),
        system_prompt=os.getenv("SYSTEM_PROMPT", "").strip(),
        max_output_tokens=max_output_tokens,
        reasoning_effort=effort,
        thinking_budget=thinking_budget,
        history_file=os.getenv("HISTORY_FILE", ".assistant_history.json").strip(),
    )
