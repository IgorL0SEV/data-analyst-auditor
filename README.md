# Data Analyst Auditor

Standalone-агент для чтения и аудита таблиц NocoDB. Читает таблицу через REST API, строит сводную статистику, генерирует графики (bar/pie) и Markdown-отчёт с LLM-выводами и рекомендациями.

## Возможности

- **Только чтение** NocoDB через REST API.
- **Автоматический профайлинг таблицы**: числовые, дата/время, категориальные и пустые колонки.
- **Графики**: bar для ≤6 категорий, pie для большего числа.
- **LLM-insights**: actionable-рекомендации на русском языке.
- **Два LLM-backend'а**: OpenAI API или любой Ollama-compatible endpoint.
- **Fallback**: если LLM не настроен или недоступен — используются встроенные rule-based выводы.

## Быстрый старт

1. Склонировать или скопировать репозиторий.
2. Создать `.env` из `.env.example`.
3. Установить зависимости:

```bash
pip install -r requirements.txt
```

4. Настроить NocoDB и LLM-backend.
5. Запустить анализ:

```bash
python scripts/analyze_nocodb.py \
  --base-id YOUR_BASE_ID \
  --table-id YOUR_TABLE_ID \
  --table-title "Название таблицы" \
  --out-dir temp/YOUR_PROJECT
```

## Настройка

Скопируйте `.env.example` → `.env` и заполните значения.

### Вариант A: OpenAI (рекомендуется для облачного использования)

```env
LLM_BACKEND=openai
OPENAI_API_KEY=***
OPENAI_MODEL=gpt-4o-mini
# Опционально: кастомный base URL для OpenAI-compatible провайдеров
# OPENAI_BASE_URL=https://api.openai.com/v1
```

### Вариант B: Ollama (локальный или self-hosted)

```env
LLM_BACKEND=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
# Опциональный API token, если Ollama-endpoint требует авторизацию
# OLLAMA_API_TOKEN=***
```

### Вариант C: без LLM

Если не задан `OPENAI_API_KEY` или недоступен Ollama-endpoint, скрипт автоматически переключается на встроенные rule-based выводы.

### NocoDB

```env
NOCODB_BASE_URL=https://nocodb.example.com
NOCODB_API_TOKEN=***
```

`base_id` и `table_id` берутся из URL дашборда NocoDB:

```
https://nocodb.example.com/dashboard/#/<workspace>/<base_id>/<table_id>/...
```

## Результаты

После запуска в `--out-dir` создаются:

- `nocodb_{base_id}_{table_id}_report.md` — полный Markdown-отчёт.
- `nocodb_{base_id}_{table_id}_summary.json` — структурированная сводка.
- `nocodb_{base_id}_{table_id}_{column}.png` — график по каждой значимой колонке.

## Пример

```bash
python scripts/analyze_nocodb.py \
  --base-id peno8v2cpubf6b7 \
  --table-id m4iak0idxqb7m43 \
  --table-title "CRM leads" \
  --out-dir temp/crm_test
```

## Структура проекта

```
data-analyst-auditor/
├── scripts/
│   ├── analyze_nocodb.py   # основной анализатор + генератор отчётов
│   ├── llm_client.py       # клиент OpenAI / Ollama
│   ├── make_chart.py       # графики matplotlib
│   ├── nocodb_client.py    # простой клиент NocoDB
│   └── shared.py           # хелперы
├── config/
│   └── settings.py         # загрузка .env
├── data/                   # примеры данных (не в Git)
├── temp/                   # сгенерированные отчёты/графики (не в Git)
├── .env.example
├── .gitignore
├── README.md
└── requirements.txt
```

## Безопасность

- Только чтение: только `GET`-запросы к NocoDB.
- Секреты не попадают в Git: `.env`, `data/`, `temp/`, `logs/` игнорируются.
- В LLM-промпт отправляется только агрегированная сводка, а не сырые строки с PII.

## Лицензия

MIT
