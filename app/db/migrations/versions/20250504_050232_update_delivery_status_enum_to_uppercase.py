"""update_delivery_status_enum_to_uppercase

Revision ID: 3141359085f7
Revises: 20250504_010000
Create Date: 2025-05-04 05:02:32.404789+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3141359085f7'
down_revision = '20250504_010000'
branch_labels = None
depends_on = None


def upgrade():
    # First drop the default value
    op.execute("ALTER TABLE delivery_tasks ALTER COLUMN status DROP DEFAULT")
    
    # Create a temporary column with the new enum type
    op.execute("ALTER TYPE delivery_task_status RENAME TO delivery_task_status_old")
    op.execute("CREATE TYPE delivery_task_status AS ENUM ('PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED')")
    
    # Update the delivery_tasks table to use the new enum type
    # Convert the existing values to their uppercase equivalents
    op.execute("""
        ALTER TABLE delivery_tasks 
        ALTER COLUMN status TYPE delivery_task_status 
        USING (
            CASE status::text
                WHEN 'pending' THEN 'PENDING'::delivery_task_status
                WHEN 'in_progress' THEN 'IN_PROGRESS'::delivery_task_status
                WHEN 'completed' THEN 'COMPLETED'::delivery_task_status
                WHEN 'failed' THEN 'FAILED'::delivery_task_status
            END
        )
    """)
    
    # Set the default value to the new uppercase value
    op.execute("ALTER TABLE delivery_tasks ALTER COLUMN status SET DEFAULT 'PENDING'::delivery_task_status")
    
    # Drop the old enum type
    op.execute("DROP TYPE delivery_task_status_old")


def downgrade():
    # First drop the default value
    op.execute("ALTER TABLE delivery_tasks ALTER COLUMN status DROP DEFAULT")
    
    # Create a temporary column with the old enum type
    op.execute("ALTER TYPE delivery_task_status RENAME TO delivery_task_status_new")
    op.execute("CREATE TYPE delivery_task_status AS ENUM ('pending', 'in_progress', 'completed', 'failed')")
    
    # Update the delivery_tasks table to use the old enum type
    # Convert the existing values to their lowercase equivalents
    op.execute("""
        ALTER TABLE delivery_tasks 
        ALTER COLUMN status TYPE delivery_task_status 
        USING (
            CASE status::text
                WHEN 'PENDING' THEN 'pending'::delivery_task_status
                WHEN 'IN_PROGRESS' THEN 'in_progress'::delivery_task_status
                WHEN 'COMPLETED' THEN 'completed'::delivery_task_status
                WHEN 'FAILED' THEN 'failed'::delivery_task_status
            END
        )
    """)
    
    # Set the default value back to the lowercase value
    op.execute("ALTER TABLE delivery_tasks ALTER COLUMN status SET DEFAULT 'pending'::delivery_task_status")
    
    # Drop the new enum type
    op.execute("DROP TYPE delivery_task_status_new")