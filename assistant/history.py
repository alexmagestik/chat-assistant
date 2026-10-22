"""История диалога с сохранением на диск между запусками."""

import json
import os
import tempfile
from datetime import datetime, timezone


class History:
    """Хранит сообщения диалога и подгружает их из JSON-файла."""

    def __init__(self, path):
        self.path = os.path.abspath(path)
        self._messages = []

    @property
    def messages(self):
        return list(self._messages)

    def __len__(self):
        return len(self._messages)

    def load(self):
        """Загружает историю с диска. Повреждённый файл не роняет приложение."""
        self._messages = []
        if not os.path.exists(self.path):
            return False
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            return False

        raw_messages = data.get("messages") if isinstance(data, dict) else data
        if not isinstance(raw_messages, list):
            return False

        for item in raw_messages:
            if (
                isinstance(item, dict)
                and item.get("role") in {"user", "assistant"}
                and isinstance(item.get("content"), str)
            ):
                self._messages.append(
                    {"role": item["role"], "content": item["content"]}
                )
        return True

    def save(self, mode=None, model=None):
        """Атомарно сохраняет историю на диск."""
        payload = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "mode": mode,
            "model": model,
            "messages": self._messages,
        }
        directory = os.path.dirname(self.path) or "."
        try:
            os.makedirs(directory, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(dir=directory, suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.path)
        except OSError:
            if "tmp_path" in locals() and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def add_user(self, content):
        self._messages.append({"role": "user", "content": content})

    def add_assistant(self, content):
        self._messages.append({"role": "assistant", "content": content})

    def pop_last(self):
        if self._messages:
            self._messages.pop()

    def reset(self):
        self._messages = []
