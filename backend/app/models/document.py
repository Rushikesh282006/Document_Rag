import enum
import uuid
from typing import TYPE_CHECKING, List, Optional, Any
from sqlalchemy import Enum as SQLEnum, ForeignKey, Integer, String, Text, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from app.core.config import settings
from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class DocumentStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Document(Base, TimestampMixin):
    """Raw document metadata tracked per tenant."""
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    file_path: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
    )
    status: Mapped[DocumentStatus] = mapped_column(
        SQLEnum(DocumentStatus, name="document_status"),
        default=DocumentStatus.PENDING,
        nullable=False,
        index=True,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="documents")
    chunks: Mapped[List["DocumentChunk"]] = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Document id={self.id} filename={self.filename} status={self.status}>"


class DocumentChunk(Base, TimestampMixin):
    """Text chunk and vector embedding strictly bound to a tenant user_id."""
    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    page_number: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    embedding: Mapped[Optional[List[float]]] = mapped_column(
        Vector(settings.EMBEDDING_DIMENSION),
        nullable=True,
    )
    chunk_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        server_default="{}",
        nullable=False,
    )

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="chunks")
    user: Mapped["User"] = relationship("User", back_populates="chunks")

    __table_args__ = (
        Index("ix_document_chunks_user_id_doc_id", "user_id", "document_id"),
    )

    def __repr__(self) -> str:
        return f"<DocumentChunk id={self.id} doc_id={self.document_id} user_id={self.user_id}>"
