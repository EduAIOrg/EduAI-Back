"""remove_chroma_collection_id

Revision ID: c3f2d250811b
Revises: 773161af94c0
Create Date: 2026-06-04 16:35:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision: str = 'c3f2d250811b'
down_revision: Union[str, None] = '773161af94c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Vérifier que la table document_chunks existe et que l'extension vector est active
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()
    
    if 'document_chunks' not in tables:
        raise RuntimeError("La table 'document_chunks' n'existe pas ! La base de données n'est pas initialisée pour pgvector.")
    
    # Vérifier l'extension vector
    res = conn.execute(sa.text("SELECT extname FROM pg_extension WHERE extname = 'vector';")).scalar()
    if not res:
        raise RuntimeError("L'extension 'vector' (pgvector) n'est pas active dans PostgreSQL.")
        
    # 2. Supprimer la colonne chroma_collection_id de la table documents
    columns = [c['name'] for c in inspector.get_columns('documents')]
    if 'chroma_collection_id' in columns:
        op.drop_column('documents', 'chroma_collection_id')


def downgrade() -> None:
    op.add_column('documents', sa.Column('chroma_collection_id', sa.String(length=255), nullable=True))
