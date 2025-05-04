"""add_updated_at_to_delivery_tasks

Revision ID: 4b234831cd40
Revises: 20250503_000000
Create Date: 2025-05-03 19:27:55.682009+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4b234831cd40'
down_revision = '20250503_000000'
branch_labels = None
depends_on = None


def upgrade():
    # Add updated_at column to delivery_tasks table
    op.add_column('delivery_tasks', 
                  sa.Column('updated_at', 
                            sa.DateTime(), 
                            nullable=False, 
                            server_default=sa.text('now()')))
    
    # Create an index on updated_at for faster queries in cleanup_failed_tasks
    op.create_index('ix_delivery_tasks_updated_at', 'delivery_tasks', ['updated_at'])


def downgrade():
    # Drop the index first
    op.drop_index('ix_delivery_tasks_updated_at', table_name='delivery_tasks')
    
    # Then drop the column
    op.drop_column('delivery_tasks', 'updated_at')