"""Bounded sanitized customer text logs."""
from alembic import op
import sqlalchemy as sa

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('attachments',
                    sa.Column('id', sa.String(36), primary_key=True),
                    sa.Column('ticket_id', sa.String(36), sa.ForeignKey('tickets.id'), nullable=False),
                    sa.Column('filename', sa.String(150), nullable=False),
                    sa.Column('content', sa.Text(), nullable=False),
                    sa.Column('content_hash', sa.String(64), nullable=False),
                    sa.Column('redacted', sa.Boolean(), nullable=False),
                    sa.Column('created_at', sa.String(40), nullable=False))
    op.create_index('ix_attachments_ticket_id', 'attachments', ['ticket_id'])


def downgrade():
    op.drop_index('ix_attachments_ticket_id', table_name='attachments')
    op.drop_table('attachments')
