import logging
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_groq import ChatGroq
from app.core.config import settings

logger = logging.getLogger(__name__)


def get_llm(temperature: float = 0.2) -> BaseChatModel:
    """Instantiate and return the configured Chat LLM with streaming support."""
    provider = settings.LLM_MODEL_PROVIDER.lower()

    if provider == "google":
        api_key = settings.GOOGLE_API_KEY.strip() if settings.GOOGLE_API_KEY else ""
        if not api_key:
            raise RuntimeError(
                "GOOGLE_API_KEY is not configured in .env. Please set your Google Gemini API key."
            )
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model="gemini-flash-lite-latest",
            temperature=temperature,
            google_api_key=api_key,
            streaming=True,
        )

    elif provider == "openai":
        api_key = settings.OPENAI_API_KEY.strip() if settings.OPENAI_API_KEY else ""
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not configured in .env. Please set your OpenAI API key."
            )
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model="gpt-4o-mini",
            temperature=temperature,
            openai_api_key=api_key,
            streaming=True,
        )

    elif provider == "groq":
        api_key = settings.GROQ_API_KEY.strip() if settings.GROQ_API_KEY else ""
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not configured in .env. Please set your Groq API key."
            )
        try:
            
            return ChatGroq(
                model=settings.GROQ_MODEL or "llama-3.3-70b-versatile",
                temperature=temperature,
                groq_api_key=api_key,
                streaming=True,
            )
        except ImportError:
            # Fallback to langchain_openai with Groq base URL (100% OpenAI compatible)
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=settings.GROQ_MODEL or "llama-3.3-70b-versatile",
                temperature=temperature,
                api_key=api_key,
                base_url="https://api.groq.com/openai/v1",
                streaming=True,
            )

    else:
        raise ValueError(
            f"Unsupported LLM_MODEL_PROVIDER: {provider}. Choose 'google', 'openai', or 'groq'."
        )
