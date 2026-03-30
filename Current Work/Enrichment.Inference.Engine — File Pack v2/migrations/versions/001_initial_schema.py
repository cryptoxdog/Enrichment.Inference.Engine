"""Initial schema: enrichment_results, convergence_runs, field_provenance, schema_proposals.

Revision ID: 001
Revises:
Create Date: 2026-03-22
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "enrichment_results",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_id", sa.String(256), nullable=False),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("domain", sa.String(128), nullable=False),
        sa.Column("fields_json", JSONB, nullable=False),
        sa.Column("confidences_json", JSONB, nullable=False),
        sa.Column("avg_confidence", sa.Float, nullable=False),
        sa.Column("null_count", sa.Integer, nullable=False),
        sa.Column("failed_matches", sa.Integer, nullable=False, default=0),
        sa.Column("last_enriched_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.Column("embedding", JSONB, nullable=True),
    )
    op.create_index("ix_er_entity_tenant", "enrichment_results", ["entity_id", "tenant_id"])
    op.create_index("ix_er_domain_stale", "enrichment_results", ["domain", "last_enriched_at"])

    op.create_table(
        "convergence_runs",
        sa.Column("run_id", sa.String(36), primary_key=True),
        sa.Column("entity_id", sa.String(256), nullable=False),
        sa.Column("domain", sa.String(128), nullable=False),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, default="running"),
        sa.Column("current_pass", sa.Integer, nullable=False, default=0),
        sa.Column("state_json", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_cr_status_domain", "convergence_runs", ["status", "domain"])

    op.create_table(
        "field_provenance",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_id", sa.String(256), nullable=False),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("field_name", sa.String(256), nullable=False),
        sa.Column("value_json", JSONB, nullable=True),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("pass_number", sa.Integer, nullable=False, default=0),
        sa.Column("run_id", sa.String(36), nullable=True),
        sa.Column("rule_id", sa.String(256), nullable=True),
        sa.Column("kb_fragment_ids", JSONB, nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_fp_entity_field", "field_provenance", ["entity_id", "field_name"])

    op.create_table(
        "schema_proposals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("domain", sa.String(128), nullable=False),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("field_name", sa.String(256), nullable=False),
        sa.Column("field_type", sa.String(64), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("fill_rate", sa.Float, nullable=False),
        sa.Column("avg_confidence", sa.Float, nullable=False),
        sa.Column("sample_values", JSONB, nullable=True),
        sa.Column("proposed_gate", JSONB, nullable=True),
        sa.Column("proposed_scoring_dimension", sa.String(256), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, default="pending"),
        sa.Column("version_bump", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_sp_domain_status", "schema_proposals", ["domain", "status"])


def downgrade() -> None:
    op.drop_table("schema_proposals")
    op.drop_table("field_provenance")
    op.drop_table("convergence_runs")
    op.drop_table("enrichment_results")
