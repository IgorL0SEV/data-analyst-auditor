#!/usr/bin/env python3
"""Simple LLM client supporting OpenAI and Ollama backends."""
import json
import os
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import settings
from scripts.shared import log


def _get_env(key, default=""):
    # Prefer agent settings, then env
    return getattr(settings, key, None) or os.environ.get(key, default)


def ollama_generate(prompt, model=None, base_url=None, api_key=None, temperature=0.3, timeout=60):
    model = model or _get_env("OLLAMA_MODEL", "kimi-k2.7-code:cloud")
    base_url = base_url or _get_env("OLLAMA_BASE_URL", "http://localhost:11434")
    url = f"{base_url.rstrip('/')}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature},
    }
    key = api_key or _get_env("OLLAMA_API_TOKEN")
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    return data.get("response", "").strip()


def openai_generate(prompt, model=None, api_key=None, base_url=None, temperature=0.3, timeout=60):
    try:
        from openai import OpenAI
    except ImportError as e:
        raise RuntimeError("openai package is required for OpenAI backend") from e

    api_key = api_key or _get_env("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not configured")
    base_url = base_url or _get_env("OPENAI_BASE_URL")
    client = OpenAI(api_key=api_key, base_url=base_url or None)
    model = model or _get_env("OPENAI_MODEL", "gpt-4o-mini")
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        timeout=timeout,
    )
    return response.choices[0].message.content.strip()


def generate(prompt, backend=None, **kwargs):
    backend = (backend or _get_env("LLM_BACKEND", "ollama")).lower()
    if backend == "openai":
        return openai_generate(prompt, **kwargs)
    if backend == "ollama":
        return ollama_generate(prompt, **kwargs)
    raise ValueError(f"Unknown LLM backend: {backend}. Use 'ollama' or 'openai'.")


def llm_insights(summary_json, row_count, table_title, backend=None):
    """Ask an LLM to write insights and recommendations for a NocoDB table summary."""
    prompt = f"""You are a data analyst. Below is a JSON summary of a NocoDB table.

Table title: {table_title}
Total rows: {row_count}

Summary:
{summary_json}

Write 3-5 concise bullet points in Russian with concrete, actionable insights and recommendations.
Do not invent numbers not in the summary. Do not include a heading or intro sentence.
Start each bullet with "- ". Keep it business-oriented.
"""
    try:
        text = generate(prompt, backend=backend)
        lines = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.lower().startswith(("ключевые выводы", "выводы", "рекомендации", "insights", "recommendations")):
                continue
            if line.startswith("- "):
                lines.append(line)
            elif line.startswith("* "):
                lines.append("- " + line[2:])
            elif line[0].isdigit() and ". " in line[:4]:
                lines.append("- " + line.split(". ", 1)[1])
            else:
                lines.append("- " + line)
        return "\n".join(lines)
    except Exception as e:
        log.warning(f"LLM insights failed ({e}); falling back to rule-based insights.")
        return None


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("prompt")
    p.add_argument("--backend", default=None)
    args = p.parse_args()
    print(generate(args.prompt, backend=args.backend))
