"""Ошибки ассистента."""


class AssistantError(Exception):
    """Базовая ошибка ассистента."""


class ConfigurationError(AssistantError):
    """Некорректная конфигурация (.env)."""


class ApiError(AssistantError):
    """Ошибка ответа ProxyAPI или конечного сервиса."""

    def __init__(self, message, status=None, code=None):
        super().__init__(message)
        self.status = status
        self.code = code


class ApiTimeoutError(AssistantError):
    """Превышено время ожидания ответа от ProxyAPI."""
