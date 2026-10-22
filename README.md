# ProxyAPI Console Assistant

Консольный ассистент для диалога с моделями ИИ через [ProxyAPI](https://api.proxyapi.ru).
Поддерживает два формата запросов, хранит историю диалога между запусками и показывает
цепочку рассуждений reasoning-моделей отдельно от ответа.

## Возможности

- **Два режима работы:**
  - OpenAI Responses — эндпоинт `/v1/responses` ([документация](https://proxyapi.ru/docs/responses))
  - Anthropic Messages — эндпоинт `/v1/messages` ([документация](https://proxyapi.ru/docs/messages))
- **Выбор модели** в рантайме, отдельная модель по умолчанию для каждого режима
  (`openai/gpt-6-luna` и `anthropic/claude-haiku-5-5`).
- **История диалога** сохраняется в JSON-файл и подгружается при следующем запуске.
- **Reasoning:** если модель рассуждающая, сначала выводится цепочка рассуждений,
  затем — итоговый ответ.
- **Надёжность:** таймауты, повторы при временных ошибках (429/5xx), понятные
  сообщения об ошибках и лог запуска.
- **Конфигурация через `.env`.**

## Требования

- Python 3.10+
- Ключ ProxyAPI

## Установка

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Зависимости: `python-dotenv`, `certifi`.

## Настройка

Скопируйте пример и укажите свой ключ:

```bash
cp .env.example .env
```

Затем отредактируйте `.env`:

```dotenv
PROXY_API_KEY=sk-...

# Базовый адрес ProxyAPI
PROXY_API_BASE=https://api.proxyapi.ru

# Режим по умолчанию: responses | messages
DEFAULT_MODE=responses

# Модели по умолчанию для каждого режима
RESPONSES_MODEL=openai/gpt-6-luna
MESSAGES_MODEL=anthropic/claude-haiku-5-5

# Системная инструкция для модели (необязательно)
SYSTEM_PROMPT=Ты полезный ассистент. Отвечай по делу на языке пользователя.

# Лимиты и таймауты
MAX_OUTPUT_TOKENS=4096
REQUEST_TIMEOUT=120
MAX_RETRIES=3

# Параметры рассуждений для reasoning-моделей
REASONING_EFFORT=medium
THINKING_BUDGET=2048

# Файл истории диалога
HISTORY_FILE=.assistant_history.json
```

### Переменные окружения

| Переменная          | По умолчанию                 | Описание                                                        |
| ------------------- | ---------------------------- | --------------------------------------------------------------- |
| `PROXY_API_KEY`     | — (обязательно)              | Ключ ProxyAPI                                                   |
| `PROXY_API_BASE`    | `https://api.proxyapi.ru`   | Базовый адрес                                                   |
| `DEFAULT_MODE`      | `responses`                  | Стартовый режим: `responses` или `messages`                     |
| `RESPONSES_MODEL`   | `openai/gpt-6-luna`          | Модель для OpenAI Responses                                     |
| `MESSAGES_MODEL`    | `anthropic/claude-haiku-5-5` | Модель для Anthropic Messages                                   |
| `SYSTEM_PROMPT`     | пусто                        | Системная инструкция (поле `instructions` / `system`)           |
| `MAX_OUTPUT_TOKENS` | `4096`                       | Лимит длины ответа                                              |
| `REQUEST_TIMEOUT`   | `120`                        | Таймаут запроса, секунды                                        |
| `MAX_RETRIES`       | `3`                          | Число попыток при временных ошибках                             |
| `REASONING_EFFORT`  | `medium`                     | Уровень рассуждений: `minimal`/`low`/`medium`/`high` (Responses) |
| `THINKING_BUDGET`   | `2048`                       | Бюджет токенов на рассуждения (Messages)                        |
| `HISTORY_FILE`      | `.assistant_history.json`    | Файл истории диалога                                            |

## Запуск

```bash
python main.py
```

Пример вывода при старте:

```text
ProxyAPI Console Assistant v1.0.0
  Режим:     OpenAI Responses (/v1/responses)
  Модель:    openai/gpt-6-luna
  Reasoning: нет
  Таймаут:   120 с, повторов: 3
  История:   пусто (.assistant_history.json)
  Введите /help для списка команд.
```

## Использование

Пишите обычный текст — он уходит модели. Для управления используйте команды:

| Команда             | Действие                                              |
| ------------------- | ----------------------------------------------------- |
| `/help`             | Справка по командам                                    |
| `/mode`             | Показать текущий режим                                 |
| `/mode responses`   | Переключиться на OpenAI Responses                      |
| `/mode messages`    | Переключиться на Anthropic Messages                    |
| `/model`            | Показать текущую модель                                |
| `/model <id>`       | Сменить модель (например `openai/gpt-5-mini`)          |
| `/models`           | Показать модели по умолчанию                           |
| `/reset`            | Очистить историю диалога                               |
| `/history`          | Показать историю диалога                               |
| `/exit`             | Выйти (также `exit`, `quit`, `Ctrl-D`)                 |

### Пример с reasoning-моделью

```text
you> /model openai/gpt-5-mini
Модель переключена: openai/gpt-5-mini (reasoning).
you> Сколько нулей в конце числа 10! ?
… ожидаю ответ модели
--- Цепочка рассуждений ---
Нужно найти количество пятёрок в разложении 10! ...
--- Ответ ---
2
   токены: вход 87, выход 86, всего 173
```

## Как это устроено

```text
main.py                 # точка входа
assistant/
  __init__.py
  config.py             # загрузка и валидация .env
  models.py             # режимы, модели по умолчанию, определение reasoning
  client.py             # HTTP-клиенты Responses и Messages, повторы, ошибки
  history.py            # загрузка/сохранение истории диалога
  cli.py                # интерактивный цикл и команды
  errors.py             # типы ошибок
```

- **История.** Сообщения хранятся в памяти и записываются на диск после каждого
  хода; при старте подгружаются из `HISTORY_FILE`. Файл пишется атомарно, поэтому
  повреждение не ломает запуск. История общая для обоих режимов.
- **Reasoning.** Модель определяется как рассуждающая по имени (известный список +
  эвристика). Для Responses добавляется объект `reasoning` со `summary: auto`,
  для Messages — `thinking` с бюджетом токенов. Из ответа извлекаются блоки
  `reasoning`/`thinking` и печатаются до текста. Если сервис не вернул
  рассуждения, выводится соответствующая пометка.
- **Ошибки.** Временные коды (429/5xx) повторяются с увеличивающейся паузой,
  таймауты и сетевые сбои обрабатываются отдельно, тело ошибки ProxyAPI
  (`detail` / `error.message`) показывается пользователю.

## Замечание по безопасности

Файл `.env` и история диалога добавлены в `.gitignore` — не коммитьте ключи
и содержимое переписки.
