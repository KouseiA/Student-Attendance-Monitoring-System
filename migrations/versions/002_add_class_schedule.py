"""Add class schedule fields

Revision ID: 002_class_schedule
Revises: 001_late_arrival
Create Date: 2024-01-01 00:00:01.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002_class_schedule'
down_revision = '001_late_arrival'
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns to class table
    with op.batch_alter_table('class', schema=None) as batch_op:
        batch_op.add_column(sa.Column('start_time', sa.Time(), nullable=False, server_default='08:00:00'))
        batch_op.add_column(sa.Column('end_time', sa.Time(), nullable=False, server_default='17:00:00'))


def downgrade():
    # Remove the added columns
    with op.batch_alter_table('class', schema=None) as batch_op:
        batch_op.drop_column('end_time')
        batch_op.drop_column('start_time')