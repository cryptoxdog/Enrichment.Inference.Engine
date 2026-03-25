"""
Sales-to-CS Handoff Document Generator.

Generates structured handoff documents when a deal closes,
compiling enrichment data, engagement history, and key contacts
into a customer success onboarding brief.

L9 Architecture Note:
    Chassis-agnostic. Receives deal + enrichment data, returns document.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class HandoffDocument:
    """Structured handoff document for CS team."""
    deal_id: str
    account_name: str
    generated_at: str
    sections: dict[str, Any] = field(default_factory=dict)
    action_items: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)


class HandoffAgent:
    """Generates sales-to-CS handoff documents from enrichment data."""

    def generate(
        self,
        deal_data: dict[str, Any],
        enrichment_data: dict[str, Any] | None = None,
        engagement_history: list[dict[str, Any]] | None = None,
    ) -> HandoffDocument:
        """
        Generate a handoff document for a closed deal.

        Sections:
        1. Account overview (from enrichment)
        2. Deal summary (stage, amount, timeline)
        3. Key contacts and stakeholders
        4. Engagement history highlights
        5. Implementation considerations
        6. Risk flags and action items
        """
        enrichment_data = enrichment_data or {}
        engagement_history = engagement_history or []

        deal_id = deal_data.get("opportunity_id", deal_data.get("id", "unknown"))
        account_name = (
            deal_data.get("account_name")
            or enrichment_data.get("company_name", "Unknown Account")
        )

        doc = HandoffDocument(
            deal_id=deal_id,
            account_name=account_name,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

        # Section 1: Account overview
        doc.sections["account_overview"] = {
            "company_name": enrichment_data.get("company_name", account_name),
            "industry": enrichment_data.get("company_industry", "Unknown"),
            "employee_count": enrichment_data.get("employee_count"),
            "location": self._build_location(enrichment_data),
            "website": enrichment_data.get("company_domain", ""),
            "description": enrichment_data.get("company_description", ""),
        }

        # Section 2: Deal summary
        doc.sections["deal_summary"] = {
            "deal_name": deal_data.get("opportunity_name", ""),
            "amount": deal_data.get("opportunity_amount"),
            "stage": deal_data.get("opportunity_stage", ""),
            "close_date": deal_data.get("opportunity_close_date", ""),
            "probability": deal_data.get("opportunity_probability"),
            "deal_type": deal_data.get("deal_type", "new_business"),
        }

        # Section 3: Key contacts
        stakeholders = deal_data.get("opportunity_stakeholders", [])
        doc.sections["key_contacts"] = [
            {
                "name": s.get("name", ""),
                "title": s.get("title", ""),
                "role": s.get("role", ""),
                "email": s.get("email", ""),
                "phone": s.get("phone", ""),
            }
            for s in stakeholders
            if isinstance(s, dict)
        ]

        # Section 4: Engagement highlights
        if engagement_history:
            recent = sorted(
                engagement_history,
                key=lambda e: e.get("date", ""),
                reverse=True,
            )[:10]
            doc.sections["engagement_highlights"] = [
                {
                    "date": e.get("date", ""),
                    "type": e.get("type", ""),
                    "summary": e.get("summary", ""),
                }
                for e in recent
            ]

        # Section 5: Implementation considerations
        doc.sections["implementation"] = {
            "tech_stack": enrichment_data.get("company_tech_stack", []),
            "integrations_needed": deal_data.get("integrations", []),
            "special_requirements": deal_data.get("special_requirements", ""),
        }

        # Section 6: Risk flags
        if not stakeholders:
            doc.risk_flags.append("No stakeholder contacts documented")
        if not enrichment_data.get("company_industry"):
            doc.risk_flags.append("Industry not identified — may affect onboarding")
        if not engagement_history:
            doc.risk_flags.append("No engagement history available")

        # Action items
        doc.action_items = [
            f"Schedule kickoff call with {account_name}",
            "Confirm primary contact for implementation",
            "Review technical requirements and integrations",
            "Set up customer success metrics and milestones",
        ]

        if doc.risk_flags:
            doc.action_items.append("Address risk flags before kickoff")

        return doc

    @staticmethod
    def _build_location(data: dict[str, Any]) -> str:
        """Build a location string from enrichment data."""
        parts = [
            data.get("company_location_city", ""),
            data.get("company_location_state", ""),
            data.get("company_location_country", ""),
        ]
        return ", ".join(p for p in parts if p)
