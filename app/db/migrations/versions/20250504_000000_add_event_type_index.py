"""add_event_type_index

Revision ID: 76543e7b9ab1
Revises: 4b234831cd40
Create Date: 2025-05-04 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '76543e7b9ab1'
down_revision = '4b234831cd40'
branch_labels = None
depends_on = None


def upgrade():
    # Add index on event_type for more efficient event type filtering
    op.create_index('ix_delivery_tasks_event_type', 'delivery_tasks', ['event_type'])
    
    # Add combined index for status + next_attempt_at for more efficient task scheduling
    op.create_index(
        'ix_delivery_tasks_status_next_attempt',
        'delivery_tasks', 
        ['status', 'next_attempt_at']
    )
    
    # Add index on subscription_id + created_at for faster subscription-specific queries
    op.create_index(
        'ix_delivery_logs_subscription_created', 
        'delivery_logs', 
        ['subscription_id', 'created_at']
    )


def downgrade():
    op.drop_index('ix_delivery_logs_subscription_created', table_name='delivery_logs')
    op.drop_index('ix_delivery_tasks_status_next_attempt', table_name='delivery_tasks')
    op.drop_index('ix_delivery_tasks_event_type', table_name='delivery_tasks')