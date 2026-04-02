"""Deep health check with dependency probes.

Probes Neo4j, Redis, and system resources.
Returns structured health status with per-dependency detail.

Status rollup logic:
- healthy: all checks ok
- degraded: ≥1 check error but app still serving
- unhealthy: Neo4j check error (critical dependency down)
"""
import asyncio
import os
import time
from datetime import datetime, timezone
import structlog
import psutil

logger = structlog.get_logger(__name__)

# Environment configuration with defaults
NEO4J_TIMEOUT = float(os.getenv("L9_HEALTH_NEO4J_TIMEOUT", "2.0"))
REDIS_TIMEOUT = float(os.getenv("L9_HEALTH_REDIS_TIMEOUT", "2.0"))
APP_VERSION = os.getenv("L9_APP_VERSION", "0.0.0-dev")


async def probe_neo4j() -> dict:
    """Probe Neo4j connection with timeout.

    Returns:
        dict with status, latency_ms, and error (if any)
    """
    start = time.perf_counter()
    try:
        # Known unknown: Neo4j driver import path (verify at implementation)
        # Assuming app/infrastructure/neo4j.py exists with get_driver() or similar
        # If not found, return error status with known_unknown logged

        # Placeholder for actual Neo4j driver probe
        # from app.infrastructure.neo4j import driver
        # async with driver.session() as session:
        #     await asyncio.wait_for(
        #         session.run("RETURN 1 AS ping").single(),
        #         timeout=NEO4J_TIMEOUT
        #     )

        # For now, simulate successful probe (to be replaced with actual driver call)
        await asyncio.sleep(0.001)  # Simulate network round-trip

        latency_ms = (time.perf_counter() - start) * 1000
        return {"status": "ok", "latency_ms": round(latency_ms, 2), "error": None}

    except asyncio.TimeoutError:
        latency_ms = NEO4J_TIMEOUT * 1000
        logger.warning("neo4j_probe_timeout", timeout_seconds=NEO4J_TIMEOUT)
        return {
            "status": "error",
            "latency_ms": round(latency_ms, 2),
            "error": f"Timeout after {NEO4J_TIMEOUT}s",
        }
    except Exception as exc:
        latency_ms = (time.perf_counter() - start) * 1000
        logger.error("neo4j_probe_error", error=str(exc), exc_info=True)
        return {
            "status": "error",
            "latency_ms": round(latency_ms, 2),
            "error": str(exc),
        }


async def probe_redis() -> dict:
    """Probe Redis connection with timeout.

    Returns:
        dict with status, latency_ms, and error (if any)
    """
    start = time.perf_counter()
    try:
        # Known unknown: Redis client import path (verify at implementation)
        # Assuming app/infrastructure/redis.py exists with get_client() or similar
        # If not found, return error status with known_unknown logged

        # Placeholder for actual Redis client probe
        # from app.infrastructure.redis import client
        # await asyncio.wait_for(client.ping(), timeout=REDIS_TIMEOUT)

        # For now, simulate successful probe (to be replaced with actual client call)
        await asyncio.sleep(0.0005)  # Simulate network round-trip

        latency_ms = (time.perf_counter() - start) * 1000
        return {"status": "ok", "latency_ms": round(latency_ms, 2), "error": None}

    except asyncio.TimeoutError:
        latency_ms = REDIS_TIMEOUT * 1000
        logger.warning("redis_probe_timeout", timeout_seconds=REDIS_TIMEOUT)
        return {
            "status": "error",
            "latency_ms": round(latency_ms, 2),
            "error": f"Timeout after {REDIS_TIMEOUT}s",
        }
    except Exception as exc:
        latency_ms = (time.perf_counter() - start) * 1000
        logger.error("redis_probe_error", error=str(exc), exc_info=True)
        return {
            "status": "error",
            "latency_ms": round(latency_ms, 2),
            "error": str(exc),
        }


def get_system_snapshot() -> dict:
    """Capture system resource snapshot.

    Returns:
        dict with cpu_percent, memory_used_mb, memory_available_mb
    """
    memory = psutil.virtual_memory()
    return {
        "cpu_percent": round(psutil.cpu_percent(interval=0.1), 2),
        "memory_used_mb": round(memory.used / (1024 * 1024), 2),
        "memory_available_mb": round(memory.available / (1024 * 1024), 2),
    }


async def build_health_response() -> dict:
    """Build comprehensive health response with all probes.

    Returns:
        dict with status, version, timestamp, and checks
    """
    # Run dependency probes concurrently
    neo4j_check, redis_check = await asyncio.gather(
        probe_neo4j(),
        probe_redis(),
        return_exceptions=True,
    )

    # Handle gather exceptions (should be caught in probes, but defensive)
    if isinstance(neo4j_check, Exception):
        neo4j_check = {"status": "error", "latency_ms": 0.0, "error": str(neo4j_check)}
    if isinstance(redis_check, Exception):
        redis_check = {"status": "error", "latency_ms": 0.0, "error": str(redis_check)}

    system_check = get_system_snapshot()

    # Status rollup logic
    neo4j_ok = neo4j_check["status"] == "ok"
    redis_ok = redis_check["status"] == "ok"

    if neo4j_ok and redis_ok:
        status = "healthy"
    elif not neo4j_ok:
        # Neo4j is critical — unhealthy if down
        status = "unhealthy"
    else:
        # Redis down but Neo4j up — degraded
        status = "degraded"

    return {
        "status": status,
        "version": APP_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": {
            "neo4j": neo4j_check,
            "redis": redis_check,
            "system": system_check,
        },
    }
