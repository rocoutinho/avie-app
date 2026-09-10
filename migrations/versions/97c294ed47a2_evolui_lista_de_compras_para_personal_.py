"""evolui lista de compras para personal shopper com status

Revision ID: 97c294ed47a2
Revises: 745d15c2273d
Create Date: 2026-09-10 14:56:01.783665

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '97c294ed47a2'
down_revision = '745d15c2273d'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('shopping_list_item', schema=None) as batch_op:
        batch_op.add_column(sa.Column('motivo', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('status', sa.String(length=20), nullable=True))

    # Converte o histórico existente: purchased=True -> 'comprada',
    # purchased=False -> 'recomendada' (estágio inicial do novo fluxo).
    shopping_list_item = sa.table(
        'shopping_list_item',
        sa.column('status', sa.String),
        sa.column('purchased', sa.Boolean),
    )
    op.execute(shopping_list_item.update().where(shopping_list_item.c.purchased.is_(True)).values(status='comprada'))
    op.execute(shopping_list_item.update().where(shopping_list_item.c.purchased.is_(False)).values(status='recomendada'))

    with op.batch_alter_table('shopping_list_item', schema=None) as batch_op:
        batch_op.alter_column('status', existing_type=sa.String(length=20), nullable=False)
        batch_op.drop_column('purchased')


def downgrade():
    with op.batch_alter_table('shopping_list_item', schema=None) as batch_op:
        batch_op.add_column(sa.Column('purchased', sa.BOOLEAN(), nullable=True))

    shopping_list_item = sa.table(
        'shopping_list_item',
        sa.column('status', sa.String),
        sa.column('purchased', sa.Boolean),
    )
    op.execute(shopping_list_item.update().where(shopping_list_item.c.status == 'comprada').values(purchased=True))
    op.execute(shopping_list_item.update().where(shopping_list_item.c.status != 'comprada').values(purchased=False))

    with op.batch_alter_table('shopping_list_item', schema=None) as batch_op:
        batch_op.alter_column('purchased', existing_type=sa.BOOLEAN(), nullable=False)
        batch_op.drop_column('status')
        batch_op.drop_column('motivo')
