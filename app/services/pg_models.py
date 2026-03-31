    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    convergence_run: Mapped[ConvergenceRun | None] = relationship(
        "ConvergenceRun", back_populates="final_result", foreign_keys=[convergence_run_id]
    )
    field_confidence_history: Mapped[list[FieldConfidenceHistory]] = relationship(
        "FieldConfidenceHistory",
        back_populates="enrichment_result",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_enrichment_results_tenant_entity", "tenant_id", "entity_id"),
        Index("ix_enrichment_results_tenant_created", "tenant_id", "created_at"),
    )


class ConvergenceRun(Base):
    """
    Tracks a full multi-pass convergence loop execution.

    Written after every pass. A restarted process loads this record and
    resumes from current_pass + 1 — full crash recovery without re-running
    completed passes.
    """

    __tablename__ = "convergence_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    domain: Mapped[str] = mapped_column(String(128), nullable=False)
    domain_yaml_version_before: Mapped[str | None] = mapped_column(String(64), nullable=True)
    domain_yaml_version_after: Mapped[str | None] = mapped_column(String(64), nullable=True)
    state: Mapped[str] = mapped_column(
        String(32), nullable=False, default="running", index=True
    )
    convergence_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    current_pass: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_passes: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    accumulated_fields: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    accumulated_confidences: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    pass_results: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_cost_usd: Mapped[float] = mapped_column(Numeric(10, 6), nullable=False, default=0.0)
    max_budget_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=50000)
    schema_proposals: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    final_result: Mapped[EnrichmentResult | None] = relationship(
        "EnrichmentResult",
        back_populates="convergence_run",
        foreign_keys=[EnrichmentResult.convergence_run_id],
        uselist=False,
    )

    __table_args__ = (
        Index("ix_convergence_runs_tenant_entity", "tenant_id", "entity_id"),
        Index("ix_convergence_runs_state", "state"),
    )


class FieldConfidenceHistory(Base):
    """Time-series per-field confidence values across enrichment passes."""

    __tablename__ = "field_confidence_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    enrichment_result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("enrichment_results.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(256), nullable=False)
    field_name: Mapped[str] = mapped_column(String(256), nullable=False)
    field_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    pass_number: Mapped[int] = mapped_column(Integer, nullable=False)
    variation_agreement: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    enrichment_result: Mapped[EnrichmentResult] = relationship(
        "EnrichmentResult", back_populates="field_confidence_history"
    )

    __table_args__ = (
        Index("ix_field_confidence_entity_field", "tenant_id", "entity_id", "field_name"),
        Index("ix_field_confidence_result_pass", "enrichment_result_id", "pass_number"),
    )


class SchemaProposalRecord(Base):
    """Schema proposals from SchemaProposer with human approval workflow."""

    __tablename__ = "schema_proposals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    domain: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    batch_run_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    field_name: Mapped[str] = mapped_column(String(256), nullable=False)
    field_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    fill_rate: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    avg_confidence: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    sample_values: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    value_distribution: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    proposed_gate: Mapped[str | None] = mapped_column(Text, nullable=True)
    proposed_scoring_dimension: Mapped[str | None] = mapped_column(Text, nullable=True)
    yaml_diff: Mapped[str | None] = mapped_column(Text, nullable=True)
    approval_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", index=True
    )
    reviewed_by: Mapped[str | None] = mapped_column(String(256), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "domain", "batch_run_id", "field_name",
            name="uq_schema_proposal_batch_field",
        ),
        Index("ix_schema_proposals_domain_status", "domain", "approval_status"),
    )
