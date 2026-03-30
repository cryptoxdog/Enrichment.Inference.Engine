"""Unit tests for provenance chain model."""

from app.models.provenance import ProvenanceChain, ProvenanceEntry, ProvenanceSource


def _entry(
    field: str, value: object, source: ProvenanceSource = ProvenanceSource.LLM
) -> ProvenanceEntry:
    return ProvenanceEntry(field_name=field, value=value, confidence=0.9, source=source)


def test_add_marks_prior_as_superseded():
    chain = ProvenanceChain(entity_id="e1", tenant_id="t1", domain="plasticos")
    e1 = _entry("material_grade", "B")
    e2 = _entry("material_grade", "A")
    chain.add(e1)
    chain.add(e2)
    assert e1.superseded_by == e2.entry_id


def test_latest_returns_most_recent():
    chain = ProvenanceChain(entity_id="e1", tenant_id="t1", domain="plasticos")
    chain.add(_entry("material_grade", "B"))
    chain.add(_entry("material_grade", "A"))
    latest = chain.latest_for("material_grade")
    assert latest.value == "A"


def test_audit_trail_ordered_oldest_first():
    chain = ProvenanceChain(entity_id="e1", tenant_id="t1", domain="plasticos")
    chain.add(_entry("density", 0.93))
    chain.add(_entry("density", 0.95))
    trail = chain.audit_trail("density")
    assert len(trail) == 2
    assert trail[0].value == 0.93


def test_gdpr_export_includes_only_active_fields():
    chain = ProvenanceChain(entity_id="e1", tenant_id="t1", domain="plasticos")
    chain.add(_entry("material_grade", "B"))
    chain.add(_entry("material_grade", "A"))  # supersedes B
    export = chain.gdpr_export()
    assert export["fields"]["material_grade"]["value"] == "A"
    assert len(export["fields"]) == 1
