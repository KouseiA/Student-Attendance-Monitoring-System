"""Add excuse request system

Revision ID: 003_excuse_requests
Revises: 002_class_schedule
Create Date: 2024-01-01 00:00:02.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision = '003_excuse_requests'
down_revision = '002_class_schedule'
branch_labels = None
depends_on = None


def upgrade():
    # Create excuse_request table
    op.create_table('excuse_request',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('class_id', sa.Integer(), nullable=False),
        sa.Column('teacher_id', sa.Integer(), nullable=False),
        sa.Column('absence_date', sa.Date(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('excuse_letter_path', sa.String(length=200), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='Pending'),
        sa.Column('submitted_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('teacher_notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['class_id'], ['class.id'], ),
        sa.ForeignKeyConstraint(['student_id'], ['student.id'], ),
        sa.ForeignKeyConstraint(['teacher_id'], ['teacher.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Add excuse_request_id column to attendance table
    with op.batch_alter_table('attendance', schema=None) as batch_op:
        batch_op.add_column(sa.Column('excuse_request_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_attendance_excuse_request', 'excuse_request', ['excuse_request_id'], ['id'])


def downgrade():
    # Remove excuse_request_id column from attendance table
    with op.batch_alter_table('attendance', schema=None) as batch_op:
        batch_op.drop_constraint('fk_attendance_excuse_request', type_='foreignkey')
        batch_op.drop_column('excuse_request_id')
    
    # Drop excuse_request table
    op.drop_table('excuse_request')