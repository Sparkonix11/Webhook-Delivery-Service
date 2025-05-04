"""update_delivery_log_status_enum_to_uppercase

Revision ID: 3cb8028f7ced
Revises: 3141359085f7
Create Date: 2025-05-04 08:08:00.108104+00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '3cb8028f7ced'
down_revision = '3141359085f7'
branch_labels = None
depends_on = None


def upgrade():
    # Create a new enum type with uppercase values
    op.execute("ALTER TYPE delivery_log_status RENAME TO delivery_log_status_old")
    op.execute("CREATE TYPE delivery_log_status AS ENUM ('SUCCESS', 'FAILED_ATTEMPT', 'FAILURE')")
    
    # Update the column to use the new enum type
    # First create a temporary text column
    op.execute("ALTER TABLE delivery_logs ADD COLUMN status_new delivery_log_status")
    
    # Copy data with uppercase values 
    op.execute("UPDATE delivery_logs SET status_new = CASE "
               "WHEN status = 'success' THEN 'SUCCESS'::delivery_log_status "
               "WHEN status = 'failed_attempt' THEN 'FAILED_ATTEMPT'::delivery_log_status "
               "WHEN status = 'failure' THEN 'FAILURE'::delivery_log_status "
               "END")
    
    # Drop the old column and rename the new one
    op.execute("ALTER TABLE delivery_logs DROP COLUMN status")
    op.execute("ALTER TABLE delivery_logs RENAME COLUMN status_new TO status")
    op.execute("ALTER TABLE delivery_logs ALTER COLUMN status SET NOT NULL")
    
    # Drop the old enum type
    op.execute("DROP TYPE delivery_log_status_old")


def downgrade():
    # Create a new enum type with lowercase values
    op.execute("ALTER TYPE delivery_log_status RENAME TO delivery_log_status_old")
    op.execute("CREATE TYPE delivery_log_status AS ENUM ('success', 'failed_attempt', 'failure')")
    
    # Update the column to use the new enum type
    # First create a temporary text column
    op.execute("ALTER TABLE delivery_logs ADD COLUMN status_new delivery_log_status")
    
    # Copy data with lowercase values
    op.execute("UPDATE delivery_logs SET status_new = CASE "
               "WHEN status = 'SUCCESS' THEN 'success'::delivery_log_status "
               "WHEN status = 'FAILED_ATTEMPT' THEN 'failed_attempt'::delivery_log_status "
               "WHEN status = 'FAILURE' THEN 'failure'::delivery_log_status "
               "END")
    
    # Drop the old column and rename the new one
    op.execute("ALTER TABLE delivery_logs DROP COLUMN status")
    op.execute("ALTER TABLE delivery_logs RENAME COLUMN status_new TO status")
    op.execute("ALTER TABLE delivery_logs ALTER COLUMN status SET NOT NULL")
    
    # Drop the old enum type
    op.execute("DROP TYPE delivery_log_status_old")