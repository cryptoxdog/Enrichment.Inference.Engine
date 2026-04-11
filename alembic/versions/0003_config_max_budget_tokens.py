"""Add max_budget_tokens to config_snapshots with backward-compatible backfill.

Revision ID: 0003
Revises: 0002
"""

from __future__ import annotations

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'config_snapshots'
                  AND column_name = 'max_budget_tokens'
            ) THEN
                ALTER TABLE config_snapshots ADD COLUMN max_budget_tokens INTEGER;
            END IF;

            UPDATE config_snapshots
            SET max_budget_tokens = COALESCE(max_budget_tokens, 50000)
            WHERE max_budget_tokens IS NULL;

            ALTER TABLE config_snapshots
                ALTER COLUMN max_budget_tokens SET DEFAULT 50000,
                ALTER COLUMN max_budget_tokens SET NOT NULL;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE config_snapshots
            ALTER COLUMN max_budget_tokens DROP NOT NULL,
            ALTER COLUMN max_budget_tokens DROP DEFAULT;
        """
    )
