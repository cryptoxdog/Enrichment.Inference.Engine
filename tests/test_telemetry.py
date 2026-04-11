"""Tests for app.core.telemetry — OpenTelemetry auto-instrumentation setup."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

otel_available = pytest.importorskip("opentelemetry", reason="opentelemetry not installed")


class TestSetupTelemetry:
    @patch.dict(
        "os.environ",
        {
            "OTEL_SERVICE_NAME": "test-enrichment",
            "OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4317",
            "ENVIRONMENT": "test",
            "VERSION": "0.1.0-test",
        },
    )
    def test_setup_instruments_app(self) -> None:
        with (
            patch("app.core.telemetry.FastAPIInstrumentor") as mock_fastapi,
            patch("app.core.telemetry.HTTPXClientInstrumentor"),
            patch("app.core.telemetry.RedisInstrumentor"),
            patch("app.core.telemetry.TracerProvider"),
            patch("app.core.telemetry.MeterProvider"),
            patch("app.core.telemetry.trace") as mock_trace,
            patch("app.core.telemetry.metrics") as mock_metrics,
        ):
            from app.core.telemetry import setup_telemetry

            app = MagicMock()
            setup_telemetry(app)

            mock_fastapi.instrument_app.assert_called_once_with(app)
            mock_trace.set_tracer_provider.assert_called_once()
            mock_metrics.set_meter_provider.assert_called_once()

    @patch.dict("os.environ", {}, clear=True)
    def test_redis_instrumentation_failure_is_non_fatal(self) -> None:
        with (
            patch("app.core.telemetry.FastAPIInstrumentor") as mock_fastapi,
            patch("app.core.telemetry.HTTPXClientInstrumentor"),
            patch("app.core.telemetry.RedisInstrumentor") as mock_redis,
            patch("app.core.telemetry.TracerProvider"),
            patch("app.core.telemetry.MeterProvider"),
            patch("app.core.telemetry.trace"),
            patch("app.core.telemetry.metrics"),
        ):
            from app.core.telemetry import setup_telemetry

            mock_redis.return_value.instrument.side_effect = RuntimeError("no redis")
            app = MagicMock()
            setup_telemetry(app)
            mock_fastapi.instrument_app.assert_called_once()
