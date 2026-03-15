"""add_product_owner_id

Revision ID: 8e607d73b2b3
Revises: 902cfb988689
Create Date: 2026-03-15 20:41:22.381708

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '8e607d73b2b3'
down_revision: str | Sequence[str] | None = '902cfb988689'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('products', sa.Column('owner_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'fk_products_owner', 'products', 'users', ['owner_id'], ['id']
    )
    op.execute(
        'UPDATE products SET owner_id = (SELECT id FROM users '
        "WHERE role = 'ADMIN' LIMIT 1)"
    )
    op.execute(
        'UPDATE products SET owner_id = (SELECT id FROM users LIMIT 1) '
        'WHERE owner_id IS NULL'
    )
    op.alter_column('products', 'owner_id', nullable=False)


def downgrade() -> None:
    op.drop_constraint('fk_products_owner', 'products', type_='foreignkey')
    op.drop_column('products', 'owner_id')
