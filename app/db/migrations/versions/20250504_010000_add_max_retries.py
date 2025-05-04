"""add max_retries column

Revision ID: 20250504_010000
Revises: add_indexes_and_constraints
Create Date: 2024-05-04 01:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20250504_010000'
down_revision = 'add_indexes_and_constraints'
branch_labels = None
depends_on = None


def upgrade():
    # Add max_retries column with default value 5
    op.add_column('delivery_tasks', sa.Column('max_retries', sa.Integer(), nullable=False, server_default='5'))


def downgrade():
    # Remove max_retries column
    op.drop_column('delivery_tasks', 'max_retries') 