"""Add safe default for missing perplexity_api_key in config_snapshots.

GAP #05: existing rows with NULL perplexity_api_key get backfilled to ''.

Revision ID: 0002
Revises: 0001
"""

from __future__ import annotations

from alembic import op  # type: ignore[attr-defined]

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='config_snapshots'
                  AND column_name='perplexity_api_key'
            ) THEN
                ALTER TABLE config_snapshots
                    ADD COLUMN perplexity_api_key TEXT NOT NULL DEFAULT '';
            ELSE
                ALTER TABLE config_snapshots
                    ALTER COLUMN perplexity_api_key SET DEFAULT '';
                UPDATE config_snapshots
                    SET perplexity_api_key = ''
                    WHERE perplexity_api_key IS NULL;
                ALTER TABLE config_snapshots
                    ALTER COLUMN perplexity_api_key SET NOT NULL;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE config_snapshots
            ALTER COLUMN perplexity_api_key DROP NOT NULL,
            ALTER COLUMN perplexity_api_key SET DEFAULT NULL;
        """
    )
