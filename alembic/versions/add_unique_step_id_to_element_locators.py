"""
添加element_locators表step_id唯一约束

Revision ID: add_unique_step_id_to_element_locators
Revises: add_view_fields_to_test_steps
Create Date: 2026-04-09
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_unique_step_id_to_element_locators'
down_revision = 'add_view_fields_to_test_steps'
branch_labels = None
depends_on = None


def upgrade():
    op.create_unique_constraint('uq_element_locators_step_id', 'element_locators', ['step_id'])


def downgrade():
    op.drop_constraint('uq_element_locators_step_id', 'element_locators', type_='unique')
