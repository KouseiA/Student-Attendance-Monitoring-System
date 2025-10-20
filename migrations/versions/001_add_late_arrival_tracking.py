"""Add late arrival tracking fields

Revision ID: 001_late_arrival
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '001_late_arrival'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns to attendance table
    with op.batch_alter_table('attendance', schema=None) as batch_op:
        batch_op.add_column(sa.Column('arrival_time', sa.Time(), nullable=True))
        batch_op.add_column(sa.Column('late_arrival', sa.Boolean(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('late_minutes', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('notes', sa.Text(), nullable=True))


def downgrade():
    # Remove the added columns
    with op.batch_alter_table('attendance', schema=None) as batch_op:
        batch_op.drop_column('notes')
        batch_op.drop_column('late_minutes')
        batch_op.drop_column('late_arrival')
        batch_op.drop_column('arrival_time')