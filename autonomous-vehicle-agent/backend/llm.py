"""Language model settings for the Research Assistant.

LLM_PROVIDER=mock (default) needs no API key: answers are composed from templates over the
retrieved records. LLM_PROVIDER=anthropic runs Claude as a tool-calling agent (research_agent.py).
LLM_PROVIDER=ollama runs a local model (default qwen2.5:7b): the rules pick the records and the model
only phrases the answer, with no API key and no data leaving the machine. Set OLLAMA_MODE=agent to let
the local model run the tool-calling agent instead (experimental: small models are unreliable at it).
LLM_PROVIDER=openai sends the retrieved records to an OpenAI model, which phrases the answer.
If a real call fails, the caller falls back to the mock answer.
"""
import os

SYSTEM_PROMPT = (
    "You are the Research Assistant for a simulated autonomous-vehicle safety agent used in a "
    "university capstone. Answer the operator's question using only the records provided. "
    "Cite the record IDs you rely on in square brackets, for example [HZ-001], [RPT-002], "
    "[ALT-001] or [INC-003]. If the records do not contain the answer, say so plainly. "
    "Do not invent vehicles, incidents, numbers or events. Keep the answer under 150 words."
)


def provider() -> str:
    return os.getenv("LLM_PROVIDER", "mock").strip().lower()


def has_credentials() -> bool:
    """True if the selected real provider has an API key configured."""
    mode = provider()
    if mode == "anthropic":
        return bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN")
                    or os.getenv("ANTHROPIC_API_KEY_HELPER"))
    if mode == "openai":
        return bool(os.getenv("OPENAI_API_KEY"))
    if mode == "ollama":
        return True  # local server, no key
    return False


def status() -> str:
    """Human-readable LLM mode for the dashboard."""
    mode = provider()
    if mode == "mock":
        return "mock"
    if not has_credentials():
        return f"mock ({mode} selected but no API key set)"
    if mode == "anthropic":
        return f"anthropic agent ({os.getenv('ANTHROPIC_MODEL', 'claude-opus-5-5')})"
    if mode == "ollama":
        kind = "agent" if os.getenv("OLLAMA_MODE") == "agent" else "local"
        return f"ollama {kind} ({os.getenv('OLLAMA_MODEL', 'qwen2.5:7b')})"
    return f"openai ({os.getenv('OPENAI_MODEL', 'gpt-4o-mini')})"


def generate(question: str, records: list[str]) -> str | None:
    """Return a grounded answer from a real LLM, or None to use the mock answer."""
    if provider() not in ("openai", "ollama"):
        return None
    prompt = "Records:\n" + "\n".join(f"- {r}" for r in records) + f"\n\nQuestion: {question}"
    return _local(prompt) if provider() == "ollama" else _openai(prompt)


def _local(prompt: str) -> str | None:
    """Phrase an answer with a local model (Ollama). Capped length and no retries so it fails fast."""
    from openai import OpenAI

    client = OpenAI(base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
                    api_key="ollama", timeout=30, max_retries=0)
    response = client.chat.completions.create(
        model=os.getenv("OLLAMA_MODEL", "qwen2.5:7b"), temperature=0, max_tokens=300,
        frequency_penalty=0.3,
        messages=[{"role": "system", "content": SYSTEM_PROMPT},
                  {"role": "user", "content": prompt}])
    if response.choices[0].finish_reason == "length":
        return None  # cut off: use the grounded rule-based answer instead
    return (response.choices[0].message.content or "").strip() or None


def _openai(prompt: str) -> str | None:
    from openai import OpenAI

    client = OpenAI()  # reads OPENAI_API_KEY from the environment
    response = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        messages=[{"role": "system", "content": SYSTEM_PROMPT},
                  {"role": "user", "content": prompt}],
    )
    return (response.choices[0].message.content or "").strip() or None
