# Data Analyst Agent — Portfolio Edition

A standalone, read-only NocoDB analyzer that reads tables, builds summary stats, creates charts (bar/pie), and generates Markdown reports with LLM-powered insights.

## Features

- **Read-only NocoDB access** via REST API.
- **Automatic table profiling**: numeric, datetime, categorical, empty columns.
- **Charts**: bar for ≤6 categories, pie for larger sets.
- **LLM insights**: actionable recommendations in Russian or English.
- **Dual LLM backend**: OpenAI API or any Ollama-compatible endpoint.
- **Fallback**: if LLM is not configured or unreachable, rule-based insights are used.

## Quick start

1. Clone/copy the repository.
2. Create `.env` from `.env.example`.
3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Configure NocoDB and LLM backend.
5. Run analysis:

```bash
python scripts/analyze_nocodb.py \
  --base-id YOUR_BASE_ID \
  --table-id YOUR_TABLE_ID \
  --table-title "Your table" \
  --out-dir temp/YOUR_PROJECT
```

## Configuration

Copy `.env.example` → `.env` and fill in your values.

### Option A: OpenAI (recommended for cloud use)

```env
LLM_BACKEND=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
# Optional: custom base URL for OpenAI-compatible providers
# OPENAI_BASE_URL=https://api.openai.com/v1
```

### Option B: Ollama (local or self-hosted)

```env
LLM_BACKEND=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
# Optional API token if your Ollama endpoint requires auth
# OLLAMA_API_TOKEN=...
```

### Option C: No LLM

If no `OPENAI_API_KEY` or reachable Ollama endpoint is configured, the script falls back to built-in rule-based insights.

### NocoDB

```env
NOCODB_BASE_URL=https://nocodb.example.com
NOCODB_API_TOKEN=your_api_token
```

Find `base_id` and `table_id` in your NocoDB dashboard URL:

```
https://nocodb.example.com/dashboard/#/<workspace>/<base_id>/<table_id>/...
```

## Outputs

For each run, the script writes to `--out-dir`:

- `nocodb_{base_id}_{table_id}_report.md` — full Markdown report.
- `nocodb_{base_id}_{table_id}_summary.json` — structured summary.
- `nocodb_{base_id}_{table_id}_{column}.png` — chart per interesting column.

## Example

```bash
python scripts/analyze_nocodb.py \
  --base-id peno8v2cpubf6b7 \
  --table-id m4iak0idxqb7m43 \
  --table-title "CRM leads" \
  --out-dir temp/crm_test
```

## Project structure

```
data-analyst-portfolio/
├── scripts/
│   ├── analyze_nocodb.py   # main analyzer + report generator
│   ├── llm_client.py       # OpenAI / Ollama client
│   ├── make_chart.py       # matplotlib charts
│   ├── nocodb_client.py    # simple NocoDB reader
│   └── shared.py           # helpers
├── config/
│   └── settings.py         # env loader
├── data/                   # sample data (not in Git)
├── temp/                   # generated reports/charts (not in Git)
├── .env.example
├── .gitignore
├── README.md
└── requirements.txt
```

## Safety

- Read-only: only `GET` requests to NocoDB.
- No secrets in Git: `.env`, `data/`, `temp/`, `logs/` are ignored.
- LLM prompts only receive aggregated summary stats, never raw rows with PII.

## License

MIT
