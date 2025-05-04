"""add indexes and constraints

Revision ID: add_indexes_and_constraints
Revises: 76543e7b9ab1
Create Date: 2024-05-03 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_indexes_and_constraints'
down_revision = '76543e7b9ab1'
branch_labels = None
depends_on = None


def upgrade():
    # Add indexes to subscriptions table
    op.create_index('ix_subscriptions_target_url', 'subscriptions', ['target_url'])
    op.create_index('ix_subscriptions_created_at', 'subscriptions', ['created_at'])
    
    # Add indexes to delivery_logs table
    op.create_index('ix_delivery_logs_status', 'delivery_logs', ['status'])
    
    # Add CASCADE delete to foreign keys
    op.drop_constraint('delivery_tasks_subscription_id_fkey', 'delivery_tasks', type_='foreignkey')
    op.create_foreign_key(
        'delivery_tasks_subscription_id_fkey',
        'delivery_tasks', 'subscriptions',
        ['subscription_id'], ['id'],
        ondelete='CASCADE'
    )
    
    op.drop_constraint('delivery_logs_delivery_task_id_fkey', 'delivery_logs', type_='foreignkey')
    op.create_foreign_key(
        'delivery_logs_delivery_task_id_fkey',
        'delivery_logs', 'delivery_tasks',
        ['delivery_task_id'], ['id'],
        ondelete='CASCADE'
    )
    
    op.drop_constraint('delivery_logs_subscription_id_fkey', 'delivery_logs', type_='foreignkey')
    op.create_foreign_key(
        'delivery_logs_subscription_id_fkey',
        'delivery_logs', 'subscriptions',
        ['subscription_id'], ['id'],
        ondelete='CASCADE'
    )


def downgrade():
    # Remove indexes from subscriptions table
    op.drop_index('ix_subscriptions_target_url')
    op.drop_index('ix_subscriptions_created_at')
    
    # Remove indexes from delivery_logs table
    op.drop_index('ix_delivery_logs_status')
    
    # Restore original foreign key constraints
    op.drop_constraint('delivery_tasks_subscription_id_fkey', 'delivery_tasks', type_='foreignkey')
    op.create_foreign_key(
        'delivery_tasks_subscription_id_fkey',
        'delivery_tasks', 'subscriptions',
        ['subscription_id'], ['id']
    )
    
    op.drop_constraint('delivery_logs_delivery_task_id_fkey', 'delivery_logs', type_='foreignkey')
    op.create_foreign_key(
        'delivery_logs_delivery_task_id_fkey',
        'delivery_logs', 'delivery_tasks',
        ['delivery_task_id'], ['id']
    )
    
    op.drop_constraint('delivery_logs_subscription_id_fkey', 'delivery_logs', type_='foreignkey')
    op.create_foreign_key(
        'delivery_logs_subscription_id_fkey',
        'delivery_logs', 'subscriptions',
        ['subscription_id'], ['id']
    ) 