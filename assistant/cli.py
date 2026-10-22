"""Интерактивный консольный интерфейс ассистента."""

import sys

from . import __version__
from .client import build_client
from .config import load_config
from .errors import ApiError, ApiTimeoutError, ConfigurationError
from .history import History
from .models import (
    DEFAULT_MESSAGES_MODEL,
    DEFAULT_RESPONSES_MODEL,
    MODE_ENDPOINTS,
    MODE_MESSAGES,
    MODE_RESPONSES,
    MODE_TITLES,
    MODES,
    is_reasoning_model,
)

EXIT_COMMANDS = {"exit", "quit", "/exit", "/quit", "/q", ":q", ":exit", ":quit"}

HELP_TEXT = """\
Команды:
  /help                 показать эту справку
  /mode                 показать текущий режим
  /mode responses       переключиться на OpenAI Responses
  /mode messages        переключиться на Anthropic Messages
  /model                показать текущую модель
  /model <id>           сменить модель (например openai/gpt-6-luna)
  /models               показать модели по умолчанию
  /reset                очистить историю диалога
  /history              показать историю диалога
  /exit                 выйти (также exit, quit, Ctrl-D)

Просто введите сообщение, чтобы отправить его модели.
"""


def _supports_color():
    return sys.stdout.isatty()


class _Painter:
    def __init__(self, enabled):
        self.enabled = enabled

    def _wrap(self, code, text):
        if not self.enabled:
            return text
        return f"\033[{code}m{text}\033[0m"

    def dim(self, text):
        return self._wrap("2", text)

    def bold(self, text):
        return self._wrap("1", text)

    def cyan(self, text):
        return self._wrap("36", text)

    def yellow(self, text):
        return self._wrap("33", text)

    def red(self, text):
        return self._wrap("31", text)


class Assistant:
    """Собирает конфигурацию, историю и клиентов в единый диалог."""

    def __init__(self, config):
        self.config = config
        self.history = History(config.history_file)
        self.models = {
            MODE_RESPONSES: config.responses_model,
            MODE_MESSAGES: config.messages_model,
        }
        self.mode = config.default_mode
        self.painter = _Painter(_supports_color())

    @property
    def model(self):
        return self.models[self.mode]

    def client(self):
        return build_client(self.mode, self.config)

    # --- запуск и логирование -------------------------------------------

    def startup_report(self):
        p = self.painter
        loaded = self.history.load()
        lines = [
            p.bold(f"ProxyAPI Console Assistant v{__version__}"),
            f"  Режим:     {p.cyan(MODE_TITLES[self.mode])} "
            f"({MODE_ENDPOINTS[self.mode]})",
            f"  Модель:    {p.cyan(self.model)}",
            f"  Reasoning: {'да' if is_reasoning_model(self.model) else 'нет'}",
            f"  Таймаут:   {self.config.timeout:g} с, повторов: {self.config.max_retries}",
        ]
        if loaded:
            lines.append(
                f"  История:   загружено {len(self.history)} "
                f"сообщений из {self.config.history_file}"
            )
        else:
            lines.append(f"  История:   пусто ({self.config.history_file})")
        lines.append("  Введите /help для списка команд.")
        print("\n".join(lines))
        print()

    def shutdown_report(self):
        self.history.save(self.mode, self.model)
        print(
            self.painter.dim(
                f"\nИстория сохранена в {self.config.history_file} "
                f"({len(self.history)} сообщений). До встречи!"
            )
        )

    # --- основной цикл ---------------------------------------------------

    def run(self):
        self.startup_report()
        while True:
            try:
                line = input(self.painter.bold("you> ")).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if not line:
                continue
            if line.lower() in EXIT_COMMANDS:
                break
            if line.startswith("/"):
                self.handle_command(line)
                continue

            self.process_message(line)

        self.shutdown_report()

    def handle_command(self, line):
        parts = line.split()
        command = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if command == "/help":
            print(HELP_TEXT)
        elif command == "/mode":
            self.command_mode(arg)
        elif command == "/model":
            self.command_model(arg)
        elif command == "/models":
            self.command_models()
        elif command == "/reset":
            self.history.reset()
            self.history.save(self.mode, self.model)
            print(self.painter.dim("История очищена."))
        elif command == "/history":
            self.command_history()
        else:
            print(self.painter.red(f"Неизвестная команда: {command}. Введите /help."))

    def command_mode(self, arg):
        if not arg:
            print(f"Текущий режим: {self.painter.cyan(MODE_TITLES[self.mode])}")
            return
        target = arg.lower()
        if target in {"openai", "responses", "response"}:
            target = MODE_RESPONSES
        elif target in {"anthropic", "messages", "message", "claude"}:
            target = MODE_MESSAGES
        if target not in MODES:
            print(self.painter.red("Доступные режимы: responses, messages."))
            return
        self.mode = target
        print(
            f"Режим переключён: {self.painter.cyan(MODE_TITLES[target])} "
            f"({MODE_ENDPOINTS[target]}), модель {self.painter.cyan(self.model)}."
        )

    def command_model(self, arg):
        if not arg:
            print(f"Текущая модель: {self.painter.cyan(self.model)}")
            return
        self.models[self.mode] = arg
        state = "reasoning" if is_reasoning_model(arg) else "обычная"
        print(f"Модель переключена: {self.painter.cyan(arg)} ({state}).")

    def command_models(self):
        print(f"  responses: {self.painter.cyan(self.config.responses_model)}")
        print(f"  messages:  {self.painter.cyan(self.config.messages_model)}")
        print(
            self.painter.dim(
                f"  (значения по умолчанию: {DEFAULT_RESPONSES_MODEL}, "
                f"{DEFAULT_MESSAGES_MODEL})"
            )
        )

    def command_history(self):
        if not self.history:
            print(self.painter.dim("История пуста."))
            return
        for message in self.history.messages:
            role = "you" if message["role"] == "user" else "ai"
            print(f"{self.painter.bold(role + '>')} {message['content']}")

    # --- запрос к модели -------------------------------------------------

    def process_message(self, text):
        self.history.add_user(text)
        reasoning = is_reasoning_model(self.model)
        p = self.painter
        try:
            print(p.dim("… ожидаю ответ модели"))
            reply = self.client().send(self.history.messages, self.model, reasoning)
        except (ApiError, ApiTimeoutError) as exc:
            self.history.pop_last()
            print(p.red(f"Ошибка запроса: {exc}"))
            return
        except KeyboardInterrupt:
            self.history.pop_last()
            print("\n" + p.yellow("Запрос отменён."))
            return

        self._render(reply)
        self.history.add_assistant(reply.text)
        self.history.save(self.mode, self.model)

    def _render(self, reply):
        p = self.painter
        reasoning = reply.reasoning.strip()
        if reasoning:
            print(p.yellow("--- Цепочка рассуждений ---"))
            print(reasoning)
            print(p.yellow("--- Ответ ---"))
        elif is_reasoning_model(reply.model):
            print(
                p.dim(
                    "— модель рассуждающая, но сервис не вернул цепочку "
                    "рассуждений —"
                )
            )
        print(p.cyan(reply.text or "(пустой ответ)"))
        usage = reply.usage or {}
        if usage:
            print(
                p.dim(
                    "   токены: "
                    f"вход {usage.get('input_tokens', '?')}, "
                    f"выход {usage.get('output_tokens', '?')}, "
                    f"всего {usage.get('total_tokens', '?')}"
                )
            )
        print()


def main():
    try:
        config = load_config()
    except ConfigurationError as exc:
        print(f"Ошибка конфигурации: {exc}", file=sys.stderr)
        return 2

    assistant = Assistant(config)
    try:
        assistant.run()
    except KeyboardInterrupt:
        assistant.shutdown_report()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
