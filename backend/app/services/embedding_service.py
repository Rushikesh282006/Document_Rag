import logging
from typing import List, Optional
from langchain_core.embeddings import Embeddings
from app.core.config import settings

logger = logging.getLogger(__name__)


class FastEmbedEmbeddings(Embeddings):
    """Local, offline, CPU-optimized embedding generation via ONNX runtime."""

    def __init__(self, model_name: str = "BAAI/bge-base-en-v1.5"):
        try:
            from fastembed import TextEmbedding
            self._model = TextEmbedding(model_name=model_name)
        except Exception as exc:
            logger.error(f"Failed to initialize FastEmbed: {exc}")
            raise

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        embeddings = list(self._model.embed(texts))
        return [e.tolist() for e in embeddings]

    def embed_query(self, text: str) -> List[float]:
        embedding = next(self._model.embed([text]))
        return embedding.tolist()


def get_embeddings_model() -> Embeddings:
    """Instantiate and return the configured vector embeddings model."""
    provider = settings.EMBEDDING_MODEL_PROVIDER.lower()

    if provider == "google":
        api_key = settings.GOOGLE_API_KEY.strip() if settings.GOOGLE_API_KEY else ""
        if not api_key:
            raise RuntimeError(
                "GOOGLE_API_KEY is not configured in .env. Please add your Google Gemini API key."
            )
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        return GoogleGenerativeAIEmbeddings(
            model="models/gemini-embedding-001",
            google_api_key=api_key,
            output_dimensionality=settings.EMBEDDING_DIMENSION,
        )

    elif provider == "openai":
        api_key = settings.OPENAI_API_KEY.strip() if settings.OPENAI_API_KEY else ""
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not configured in .env. Please add your OpenAI API key."
            )
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=api_key,
            dimensions=settings.EMBEDDING_DIMENSION,
        )

    elif provider in ("huggingface", "hf", "fastembed", "local"):
        model_name = settings.HUGGINGFACE_EMBEDDING_MODEL or "BAAI/bge-base-en-v1.5"
        try:
            return FastEmbedEmbeddings(model_name=model_name)
        except Exception as exc:
            logger.warning(f"FastEmbed initialization error: {exc}. Trying fallback...")
            try:
                from langchain_community.embeddings import HuggingFaceEmbeddings
                return HuggingFaceEmbeddings(
                    model_name=model_name,
                    model_kwargs={"device": "cpu"},
                    encode_kwargs={"normalize_embeddings": True},
                )
            except Exception as e2:
                raise RuntimeError(
                    f"Failed to load embedding model '{model_name}': {exc}; fallback error: {e2}"
                )

    else:
        raise ValueError(
            f"Unsupported EMBEDDING_MODEL_PROVIDER: {provider}. Choose 'google', 'openai', or 'huggingface'."
        )


class EmbeddingService:
    """Service wrapping batch embedding generation with lazy model initialization."""

    def __init__(self, embeddings_model: Optional[Embeddings] = None):
        self._model = embeddings_model

    @property
    def model(self) -> Embeddings:
        """Lazily initialize the embedding model only when required."""
        if self._model is None:
            self._model = get_embeddings_model()
        return self._model

    def generate_embeddings(self, texts: List[str], batch_size: int = 50) -> List[List[float]]:
        """Generate vector embeddings for a list of strings in batches."""
        if not texts:
            return []

        all_embeddings: List[List[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            embeddings = self.model.embed_documents(batch)
            all_embeddings.extend(embeddings)

        return all_embeddings

    def generate_query_embedding(self, query: str) -> List[float]:
        """Generate vector embedding for a single search query."""
        return self.model.embed_query(query)
