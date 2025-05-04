"""Initial migration

Revision ID: 20250503_000000
Revises: 
Create Date: 2023-05-03 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20250503_000000'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create subscriptions table
    op.create_table(
        'subscriptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('target_url', sa.String(), nullable=False),
        sa.Column('secret', sa.String(), nullable=True),
        sa.Column('event_types', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_subscriptions_id', 'subscriptions', ['id'])
    
    # Create delivery_tasks table
    op.create_table(
        'delivery_tasks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('subscription_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('event_type', sa.String(), nullable=True),
        sa.Column('status', sa.Enum('pending', 'in_progress', 'completed', 'failed', name='delivery_task_status'), 
                  nullable=False, server_default='pending'),
        sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('next_attempt_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['subscription_id'], ['subscriptions.id'], ),
    )
    op.create_index('ix_delivery_tasks_id', 'delivery_tasks', ['id'])
    op.create_index('ix_delivery_tasks_subscription_id', 'delivery_tasks', ['subscription_id'])
    op.create_index('ix_delivery_tasks_status', 'delivery_tasks', ['status'])
    op.create_index('ix_delivery_tasks_next_attempt_at', 'delivery_tasks', ['next_attempt_at'])
    
    # Create delivery_logs table
    op.create_table(
        'delivery_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('delivery_task_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('subscription_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('target_url', sa.String(), nullable=False),
        sa.Column('attempt_number', sa.Integer(), nullable=False),
        sa.Column('status', sa.Enum('success', 'failed_attempt', 'failure', name='delivery_log_status'), nullable=False),
        sa.Column('status_code', sa.Integer(), nullable=True),
        sa.Column('error_details', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['delivery_task_id'], ['delivery_tasks.id'], ),
        sa.ForeignKeyConstraint(['subscription_id'], ['subscriptions.id'], ),
    )
    op.create_index('ix_delivery_logs_id', 'delivery_logs', ['id'])
    op.create_index('ix_delivery_logs_delivery_task_id', 'delivery_logs', ['delivery_task_id'])
    op.create_index('ix_delivery_logs_subscription_id', 'delivery_logs', ['subscription_id'])
    op.create_index('ix_delivery_logs_created_at', 'delivery_logs', ['created_at'])


def downgrade():
    op.drop_table('delivery_logs')
    op.drop_table('delivery_tasks')
    op.drop_table('subscriptions')
    op.execute('DROP TYPE IF EXISTS delivery_log_status')
    op.execute('DROP TYPE IF EXISTS delivery_task_status')