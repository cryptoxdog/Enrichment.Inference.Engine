"""Health package — CRM data quality assessment and field diagnostics.

Exports:
    HealthAssessor       — Core assessment engine
    HealthWeights        — Dimension weighting configuration
    AssessmentConfig     — Assessment parameters
    AssessmentScope      — Scope definition (entity vs CRM-wide)
    FieldHealth          — Per-field health metrics
    TriggerEngine        — Automated trigger dispatch
    run_field_diagnostic — Field-level diagnostic analysis
    configure            — Module initialization (call at startup)
"""

from .health_api import configure
from .health_assessor import DomainSchema, EntityDataStore, HealthAssessor
from .health_field_analyzer import run_field_diagnostic
from .health_models import (
    AssessmentConfig,
    AssessmentScope,
    FieldHealth,
    HealthWeights,
)
from .health_triggers import TriggerEngine

__all__ = [
    "AssessmentConfig",
    "AssessmentScope",
    "DomainSchema",
    "EntityDataStore",
    "FieldHealth",
    "HealthAssessor",
    "HealthWeights",
    "TriggerEngine",
    "configure",
    "run_field_diagnostic",
]
