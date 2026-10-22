"""Режимы работы, каталог моделей и определение reasoning-моделей."""

MODE_RESPONSES = "responses"
MODE_MESSAGES = "messages"
MODES = (MODE_RESPONSES, MODE_MESSAGES)

MODE_TITLES = {
    MODE_RESPONSES: "OpenAI Responses",
    MODE_MESSAGES: "Anthropic Messages",
}

MODE_ENDPOINTS = {
    MODE_RESPONSES: "/v1/responses",
    MODE_MESSAGES: "/v1/messages",
}

DEFAULT_RESPONSES_MODEL = "openai/gpt-6-luna"
DEFAULT_MESSAGES_MODEL = "anthropic/claude-haiku-5-5"

# Известные модели и их способность к рассуждениям.
# Для моделей вне списка работает эвристика по имени.
KNOWN_REASONING_MODELS = {
    "openai/gpt-5": True,
    "openai/gpt-5-mini": True,
    "openai/o1": True,
    "openai/o3": True,
    "openai/o4-mini": True,
    "deepseek/deepseek-r1": True,
    "deepseek/deepseek-v4-pro": True,
    "qwen/qwq": True,
    "anthropic/claude-haiku-5-5": False,
    "openai/gpt-6-luna": False,
}

_REASONING_MARKERS = (
    "reason",
    "thinking",
    "think",
    "o1",
    "o3",
    "o4",
    "qwq",
    "-r1",
    "gpt-5",
    "sonnet-4",
    "opus-4",
)

_NON_REASONING_MARKERS = (
    "gpt-4",
    "gpt-6-luna",
    "haiku",
    "flash",
    "mini",
)


def is_reasoning_model(model):
    """Определяет, является ли модель рассуждающей."""
    if not model:
        return False
    key = model.strip().lower()
    if key in KNOWN_REASONING_MODELS:
        return KNOWN_REASONING_MODELS[key]

    name = key.split("/")[-1]
    if any(marker in name for marker in _NON_REASONING_MARKERS):
        return False
    return any(marker in name for marker in _REASONING_MARKERS)
