"""Persist command idempotency without appending command history."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "command_receipts",
        sa.Column("merchant_id", sa.String(), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column(
            "conversation_id", sa.String(), sa.ForeignKey("conversations.id"), nullable=False
        ),
        sa.Column("client_message_id", sa.String(64), nullable=False),
        sa.Column("workflow", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("conversation_id", "client_message_id"),
    )
    op.create_index("ix_command_receipts_merchant_id", "command_receipts", ["merchant_id"])


def downgrade():
    op.drop_index("ix_command_receipts_merchant_id", table_name="command_receipts")
    op.drop_table("command_receipts")
