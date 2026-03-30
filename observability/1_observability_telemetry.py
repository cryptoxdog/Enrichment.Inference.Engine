"""
OpenTelemetry Auto-Instrumentation for FastAPI
Implements: Gap Analysis P1-1 (Observability 25% → 60%)

This module provides automatic distributed tracing, metrics, and context propagation
for FastAPI applications using OpenTelemetry.

Installation:
    pip install opentelemetry-distro opentelemetry-exporter-otlp
    pip install opentelemetry-instrumentation-fastapi
    pip install opentelemetry-instrumentation-httpx
    pip install opentelemetry-instrumentation-redis

Environment Variables:
    OTEL_SERVICE_NAME: Service name (default: graph-engine)
    OTEL_EXPORTER_OTLP_ENDPOINT: Collector endpoint (default: http://localhost:4317)
    OTEL_TRACES_EXPORTER: Trace exporter (default: otlp)
    OTEL_METRICS_EXPORTER: Metrics exporter (default: otlp)
    OTEL_LOGS_EXPORTER: Logs exporter (default: none)
    ENVIRONMENT: Deployment environment (dev/staging/prod)

Usage:
    from engine.api.app import create_app
    from engine.observability import setup_telemetry

    app = create_app()
    setup_telemetry(app)
"""

import logging
import os

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

logger = logging.getLogger(__name__)


def setup_telemetry(app, service_name: str | None = None) -> None:
    """
    Configure OpenTelemetry auto-instrumentation for FastAPI.

    This sets up:
    - Distributed tracing with automatic span creation for HTTP requests
    - Metrics collection (request count, latency, error rate)
    - Context propagation across service boundaries
    - Automatic instrumentation for httpx and Redis clients

    Args:
        app: FastAPI application instance
        service_name: Service identifier (overrides OTEL_SERVICE_NAME env var)
    """
    # Resolve service name
    service_name = service_name or os.getenv("OTEL_SERVICE_NAME", "graph-engine")
    environment = os.getenv("ENVIRONMENT", "development")

    # Create resource with service metadata
    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": os.getenv("VERSION", "unknown"),
            "deployment.environment": environment,
        }
    )

    # Setup tracing
    _setup_tracing(resource)

    # Setup metrics
    _setup_metrics(resource)

    # Instrument FastAPI
    FastAPIInstrumentor.instrument_app(app)

    # Instrument outbound HTTP clients
    HTTPXClientInstrumentor().instrument()

    # Instrument Redis (if available)
    try:
        RedisInstrumentor().instrument()
    except Exception as e:
        logger.warning(f"Redis instrumentation failed (skipped): {e}")

    logger.info(
        f"OpenTelemetry initialized: service={service_name}, "
        f"environment={environment}, "
        f"endpoint={os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT', 'default')}"
    )


def _setup_tracing(resource: Resource) -> None:
    """Configure distributed tracing."""
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

    # Create OTLP span exporter
    span_exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)

    # Create tracer provider with batch processor
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))

    # Set global tracer provider
    trace.set_tracer_provider(tracer_provider)


def _setup_metrics(resource: Resource) -> None:
    """Configure metrics collection."""
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

    # Create OTLP metric exporter
    metric_exporter = OTLPMetricExporter(endpoint=endpoint, insecure=True)

    # Create metric reader with 60s export interval
    metric_reader = PeriodicExportingMetricReader(metric_exporter, export_interval_millis=60_000)

    # Create meter provider
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])

    # Set global meter provider
    metrics.set_meter_provider(meter_provider)
