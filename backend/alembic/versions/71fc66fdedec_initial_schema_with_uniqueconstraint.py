"""Initial schema with UniqueConstraint

Revision ID: 71fc66fdedec
Revises: 
Create Date: 2026-09-22 22:06:51.866292

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '71fc66fdedec'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('daily_usage') as batch_op:
        batch_op.create_unique_constraint('uix_identifier_date', ['identifier', 'date_str'])


def downgrade() -> None:
    with op.batch_alter_table('daily_usage') as batch_op:
        batch_op.drop_constraint('uix_identifier_date', type_='unique')
