"""Application settings, read once from environment variables / a .env file.

The single most important setting is LLM_PROVIDER ("ollama" or "openai"): it is
the one switch that moves the whole application between the local Qwen2.5:3B
deployment and the OpenAI cloud deployment, with no code changes.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    # --- model providers ---
    llm_provider: str = "ollama"
    ollama_model: str = "qwen2.5:3b"
    ollama_base_url: str = "http://localhost:11434"
    ollama_num_ctx: int = 8192
    openai_model: str = "gpt-4o-mini"
    openai_api_key: str = ""

    # --- external services ---
    tavily_api_key: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""

    # --- storage ---
    data_dir: Path = ROOT / "data"

    # --- execution limits (every loop in the system is bounded) ---
    max_supervisor_steps: int = 8      # Supervisor decisions per user turn
    max_sql_retries: int = 3           # failed SQL attempts before the Analyst gives up
    max_research_cycles: int = 4       # Thought/Action/Observation cycles for Research
    recursion_limit: int = 60          # LangGraph's global safety net

    # --- SQL tool safety ---
    sql_row_limit: int = 200
    sql_timeout_seconds: int = 20

    # --- conversation memory ---
    trim_max_tokens: int = 3000        # budget for the history sent to the LLM
    summarize_after_messages: int = 24  # start summarising older turns after this many
    keep_recent_messages: int = 8      # always keep this many recent messages verbatim

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(ROOT / ".env")
        g = os.environ.get
        return cls(
            llm_provider=g("LLM_PROVIDER", "ollama").strip().lower(),
            ollama_model=g("OLLAMA_MODEL", "qwen2.5:3b"),
            ollama_base_url=g("OLLAMA_BASE_URL", "http://localhost:11434"),
            ollama_num_ctx=int(g("OLLAMA_NUM_CTX", "8192")),
            openai_model=g("OPENAI_MODEL", "gpt-4o-mini"),
            openai_api_key=g("OPENAI_API_KEY", ""),
            tavily_api_key=g("TAVILY_API_KEY", ""),
            smtp_host=g("SMTP_HOST", ""),
            smtp_port=int(g("SMTP_PORT", "587") or 587),
            smtp_user=g("SMTP_USER", ""),
            smtp_password=g("SMTP_PASSWORD", ""),
            smtp_from=g("SMTP_FROM", ""),
            data_dir=Path(g("INSIGHTPILOT_DATA_DIR", str(ROOT / "data"))),
        )

    def with_overrides(self, **kw) -> "Settings":
        return replace(self, **kw)


def get_settings() -> Settings:
    return Settings.from_env()
