"""
Multi-source waterfall enrichment engine with quality-based fallback.

Orchestrates enrichment across multiple sources in priority order,
stopping when quality thresholds are met or all sources are exhausted.

The engine uses the existing Perplexity Sonar client as its primary
source, with the BaseSource interface allowing additional sources
(Clearbit, ZoomInfo, Apollo, etc.) to be added as adapters.

L9 Architecture Note:
    This module is chassis-agnostic. It never imports FastAPI.
    It is called by the enrichment_orchestrator during the
    enrichment phase of the convergence loop.
"""

from __future__ import annotations

from typing import Any

import structlog
import yaml

from .quality_scorer import QualityScorer
from .sources.base import BaseSource, EnrichmentResult, SourceConfig
from .sources import SOURCE_REGISTRY
from .sources.perplexity_adapter import PerplexitySonarSource

logger = structlog.get_logger("waterfall_engine")


class WaterfallEngine:
    """
    Orchestrates multi-source enrichment for a given domain using a
    configured waterfall strategy with quality thresholds.

    Currently supports:
    - perplexity_sonar (via existing perplexity_client.py)

    Additional sources can be registered via register_source().
    """

    def __init__(
        self,
        sources_config_path: str | None = None,
        quality_thresholds_path: str | None = None,
        perplexity_api_key: str | None = None,
        breaker: Any | None = None,
    ) -> None:
        self.quality_scorer = QualityScorer(quality_thresholds_path)
        self.source_clients: dict[str, BaseSource] = {}
        self._waterfall_cfg: dict[str, Any] = {}
        self._fallback_cfg: dict[str, Any] = {}

        # Load waterfall config if provided
        if sources_config_path:
            self._load_config(sources_config_path)

        # Always register the Perplexity source if key is available
        if perplexity_api_key:
            self._register_perplexity(perplexity_api_key, breaker)

    def _load_config(self, path: str) -> None:
        """Load waterfall strategy and fallback config from YAML."""
        try:
            with open(path) as f:
                cfg = yaml.safe_load(f) or {}
        except FileNotFoundError:
            logger.warning("waterfall_config_not_found", path=path)
            return

        self._waterfall_cfg = cfg.get("waterfall_strategies", {})
        self._fallback_cfg = cfg.get("fallback_behavior", {})

    def auto_register_sources(
        self, provider_config_path: str = "config/provider_config.yaml"
    ) -> None:
        """
        Auto-register enrichment sources from provider_config.yaml.

        Reads the config file and instantiates source classes from the
        SOURCE_REGISTRY for any provider that has enabled=true and a
        valid api_key.
        """
        try:
            with open(provider_config_path) as f:
                cfg = yaml.safe_load(f) or {}
        except FileNotFoundError:
            logger.warning("provider_config_not_found", path=provider_config_path)
            return

        providers = cfg.get("providers", {})
        for name, pcfg in providers.items():
            if not pcfg.get("enabled", False):
                continue
            api_key = pcfg.get("api_key", "")
            if not api_key or api_key.startswith("${"):
                continue  # Placeholder — not configured

            source_cls = SOURCE_REGISTRY.get(name)
            if not source_cls:
                logger.warning("unknown_source_provider", name=name)
                continue

            if name in self.source_clients:
                continue  # Already registered (e.g. perplexity)

            config = SourceConfig(
                name=name,
                enabled=True,
                api_endpoint=pcfg.get("base_url", ""),
                auth_type=pcfg.get("auth_type", "api_key"),
                api_key=api_key,
                timeout=pcfg.get("timeout", 30),
                retry_count=pcfg.get("retry_count", 2),
                supported_domains=pcfg.get("supported_domains", ["company", "contact"]),
                quality_tier=pcfg.get("quality_tier", "standard"),
            )
            self.source_clients[name] = source_cls(config=config)
            logger.info("auto_registered_source", name=name)

    def _register_perplexity(
        self, api_key: str, breaker: Any | None
    ) -> None:
        """Register the Perplexity Sonar source."""
        config = SourceConfig(
            name="perplexity_sonar",
            enabled=True,
            api_endpoint="https://api.perplexity.ai",
            auth_type="bearer",
            api_key=api_key,
            timeout=60,
            retry_count=3,
            supported_domains=[
                "company",
                "contact",
                "account",
                "opportunity",
            ],
            quality_tier="ai_inference",
        )
        self.source_clients["perplexity_sonar"] = PerplexitySonarSource(
            config=config,
            breaker=breaker,
        )

    def register_source(self, name: str, source: BaseSource) -> None:
        """Register an additional enrichment source."""
        self.source_clients[name] = source
        logger.info("source_registered", name=name)

    async def enrich(
        self,
        domain: str,
        input_payload: dict[str, Any],
    ) -> tuple[dict[str, Any], float, list[EnrichmentResult]]:
        """
        Execute waterfall enrichment for a given domain.

        Sources are called in priority order. Enrichment stops when:
        - Quality threshold is met
        - Max attempts are exhausted
        - All sources are tried

        Returns:
            merged_data: canonical enriched fields
            quality_score: final quality score (0-1)
            results: per-source enrichment results
        """
        strategy = self._waterfall_cfg.get(domain)
        max_attempts = 3
        min_quality = 0.8

        if strategy:
            max_attempts = strategy.get("max_attempts", 3)
            min_quality = strategy.get("quality_threshold", 0.8)

        merged: dict[str, Any] = dict(input_payload)
        results: list[EnrichmentResult] = []
        used_quality: list[float] = []

        # Determine source order
        source_order = self._get_source_order(domain, strategy)

        attempt = 0
        for source_name in source_order:
            if attempt >= max_attempts:
                break
            attempt += 1

            src = self.source_clients.get(source_name)
            if not src or not src.config.enabled:
                continue
            if (
                domain not in src.config.supported_domains
                and src.config.quality_tier != "ai_inference"
            ):
                continue

            result = await self._call_source(src, domain, merged)
            results.append(result)

            if result.error:
                logger.warning(
                    "source_failed",
                    source=source_name,
                    error=result.error,
                )
                continue

            # Merge non-empty fields
            for k, v in result.data.items():
                if v not in (None, "", [], {}):
                    merged[k] = v

            used_quality.append(result.quality_score)

            # Check if we already meet quality threshold
            current = self.quality_scorer.score(
                domain, merged, used_quality
            )
            if current >= min_quality:
                logger.info(
                    "quality_threshold_met",
                    domain=domain,
                    quality=current,
                    sources_used=attempt,
                )
                break

        # Final quality score
        final_quality = self.quality_scorer.score(
            domain, merged, used_quality
        )

        # Fallback signaling
        if final_quality < min_quality:
            fb = self._fallback_cfg.get("on_quality_below_threshold")
            if fb == "use_inference_bridge":
                logger.info(
                    "signaling_inference_bridge",
                    domain=domain,
                    quality=final_quality,
                )

        # Inject provenance
        merged["enrichment_sources_used"] = [
            r.source_name for r in results if not r.error
        ]
        merged["enrichment_quality_score"] = final_quality

        return merged, final_quality, results

    def _get_source_order(
        self,
        domain: str,
        strategy: dict[str, Any] | None,
    ) -> list[str]:
        """Determine source execution order from config or defaults."""
        if strategy and "sources" in strategy:
            return [s["name"] for s in strategy["sources"]]
        # Default: all registered sources
        return list(self.source_clients.keys())

    @staticmethod
    async def _call_source(
        src: BaseSource,
        domain: str,
        payload: dict[str, Any],
    ) -> EnrichmentResult:
        """Call a single enrichment source with error handling."""
        try:
            return await src.enrich(domain, payload)
        except Exception as exc:
            logger.error(
                "source_exception",
                source=src.config.name,
                error=str(exc),
            )
            return EnrichmentResult(
                data={},
                quality_score=0.0,
                source_name=src.config.name,
                latency_ms=0,
                error=str(exc),
            )
