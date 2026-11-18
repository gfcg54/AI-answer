from langchain_openai import ChatOpenAI

from app.core.config import get_settings
from app.core.exceptions import AIConfigurationError


def create_chat_model(temperature: float) -> ChatOpenAI:
    settings = get_settings()
    if settings.deepseek_api_key is None:
        raise AIConfigurationError()

    return ChatOpenAI(
        model=settings.deepseek_model,
        base_url=settings.deepseek_base_url,
        api_key=settings.deepseek_api_key.get_secret_value(),
        temperature=temperature,
        timeout=settings.llm_timeout_seconds,
        max_retries=1,
        extra_body={"thinking": {"type": "disabled"}},
    )
