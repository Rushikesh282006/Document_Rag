"""initial schema with users, documents, and document_chunks

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-10-08 14:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import pgvector
from pgvector.sqlalchemy import Vector

from app.core.config import settings

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # 2. Create users table
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    # 3. Create document_status enum & documents table
    document_status = postgresql.ENUM("PENDING", "PROCESSING", "COMPLETED", "FAILED", name="document_status", create_type=False)
    op.execute("DO $$ BEGIN CREATE TYPE document_status AS ENUM ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED'); EXCEPTION WHEN duplicate_object THEN null; END $$;")

    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=1024), nullable=False),
        sa.Column(
            "status",
            document_status,
            nullable=False,
            server_default="PENDING",
        ),

        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f("ix_documents_user_id"), "documents", ["user_id"], unique=False)
    op.create_index(op.f("ix_documents_status"), "documents", ["status"], unique=False)

    # 4. Create document_chunks table with pgvector column
    op.create_table(
        "document_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("embedding", Vector(settings.EMBEDDING_DIMENSION), nullable=True),
        sa.Column("chunk_metadata", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f("ix_document_chunks_document_id"), "document_chunks", ["document_id"], unique=False)
    op.create_index(op.f("ix_document_chunks_user_id"), "document_chunks", ["user_id"], unique=False)
    op.create_index(
        "ix_document_chunks_user_id_doc_id",
        "document_chunks",
        ["user_id", "document_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_document_chunks_user_id_doc_id", table_name="document_chunks")
    op.drop_index(op.f("ix_document_chunks_user_id"), table_name="document_chunks")
    op.drop_index(op.f("ix_document_chunks_document_id"), table_name="document_chunks")
    op.drop_table("document_chunks")

    op.drop_index(op.f("ix_documents_status"), table_name="documents")
    op.drop_index(op.f("ix_documents_user_id"), table_name="documents")
    op.drop_table("documents")

    document_status = postgresql.ENUM("PENDING", "PROCESSING", "COMPLETED", "FAILED", name="document_status")
    document_status.drop(op.get_bind(), checkfirst=True)

    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
