"""Language model settings for the Research Assistant.

LLM_PROVIDER=mock (default) needs no API key: answers are composed from templates over the
retrieved records. LLM_PROVIDER=anthropic runs Claude as a tool-calling agent (research_agent.py).
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
    return f"openai ({os.getenv('OPENAI_MODEL', 'gpt-4o-mini')})"


def generate(question: str, records: list[str]) -> str | None:
    """Return a grounded answer from a real LLM, or None to use the mock answer."""
    if provider() != "openai":
        return None
    prompt = "Records:\n" + "\n".join(f"- {r}" for r in records) + f"\n\nQuestion: {question}"
    return _openai(prompt)


def _openai(prompt: str) -> str | None:
    from openai import OpenAI

    client = OpenAI()  # reads OPENAI_API_KEY from the environment
    response = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        messages=[{"role": "system", "content": SYSTEM_PROMPT},
                  {"role": "user", "content": prompt}],
    )
    return (response.choices[0].message.content or "").strip() or None
