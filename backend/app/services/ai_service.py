from app.core.config import settings
from app.services.ollama_service import ask_ollama
from app.services.openai_service import ask_ai as ask_openai


def ask_ai(prompt: str) -> str:
    provider = settings.AI_PROVIDER.lower().strip()

    if provider == "ollama":
        return ask_ollama(prompt)
    if provider == "openai":
        return ask_openai(prompt)

    raise RuntimeError(
        f"Unsupported AI_PROVIDER '{settings.AI_PROVIDER}'. "
        "Use 'ollama' or 'openai'."
    )
