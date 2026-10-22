import logging
from typing import List, Optional
from langchain_core.embeddings import Embeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from app.core.config import settings

logger = logging.getLogger(__name__)


def get_embeddings_model() -> Embeddings:
    """Instantiate and return the configured vector embeddings model."""
    provider = settings.EMBEDDING_MODEL_PROVIDER.lower()

    if provider == "google":
        api_key = settings.GOOGLE_API_KEY.strip() if settings.GOOGLE_API_KEY else ""
        if not api_key:
            raise RuntimeError(
                "GOOGLE_API_KEY is not configured in .env. Please add your Google Gemini API key."
            )
        
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

    elif provider in ("huggingface", "hf"):
        model_name = settings.HUGGINGFACE_EMBEDDING_MODEL or "BAAI/bge-base-en-v1.5"
        api_key = settings.HUGGINGFACE_API_KEY.strip() if settings.HUGGINGFACE_API_KEY else ""

        if api_key:
            # Free Serverless Hugging Face Inference API
            try:
                from langchain_huggingface import HuggingFaceEndpointEmbeddings
                return HuggingFaceEndpointEmbeddings(
                    model=model_name,
                    huggingfacehub_api_token=api_key,
                )
            except ImportError:
                from langchain_community.embeddings import HuggingFaceInferenceAPIEmbeddings
                return HuggingFaceInferenceAPIEmbeddings(
                    api_key=api_key,
                    model_name=model_name,
                )
        else:
            # Local sentence-transformers execution (100% free, runs offline on CPU)
            try:
                from langchain_community.embeddings import HuggingFaceEmbeddings
                return HuggingFaceEmbeddings(
                    model_name=model_name,
                    model_kwargs={"device": "cpu"},
                    encode_kwargs={"normalize_embeddings": True},
                )
            except Exception as e:
                raise RuntimeError(
                    f"To use local HuggingFace embeddings without an API key, install sentence-transformers: 'pip install sentence-transformers'. "
                    f"Or provide a free HUGGINGFACE_API_KEY in your .env file. Error: {e}"
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
