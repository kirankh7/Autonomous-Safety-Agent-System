"""Language model used to phrase Research Assistant answers.

LLM_PROVIDER=mock (default) needs no API key: answers are composed from templates over the
retrieved records. LLM_PROVIDER=anthropic or openai sends the same records to a real model,
which must answer only from them. If a real call fails, the caller falls back to the mock answer.
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


def generate(question: str, records: list[str]) -> str | None:
    """Return a grounded answer from a real LLM, or None to use the mock answer."""
    mode = provider()
    if mode == "mock":
        return None
    prompt = "Records:\n" + "\n".join(f"- {r}" for r in records) + f"\n\nQuestion: {question}"
    if mode == "anthropic":
        return _anthropic(prompt)
    if mode == "openai":
        return _openai(prompt)
    return None


def _anthropic(prompt: str) -> str | None:
    import anthropic

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment
    response = client.beta.messages.create(
        model=os.getenv("ANTHROPIC_MODEL", "claude-opus-5-5"),
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
        output_config={"effort": "low"},
        # Server-side fallback: if the model declines, the API retries on a suitable model.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if response.stop_reason == "refusal":
        return None
    text = "".join(block.text for block in response.content if block.type == "text").strip()
    return text or None


def _openai(prompt: str) -> str | None:
    from openai import OpenAI

    client = OpenAI()  # reads OPENAI_API_KEY from the environment
    response = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        messages=[{"role": "system", "content": SYSTEM_PROMPT},
                  {"role": "user", "content": prompt}],
    )
    return (response.choices[0].message.content or "").strip() or None
