# Observability Runbook — Enrichment Inference Engine

**Version:** 1.0  
**Last Updated:** 2026-04-02  
**Owner:** Platform Team

This runbook maps alert conditions to remediation actions using Prometheus metrics.
All PromQL expressions are verified against the metric schema in `app/observability/metrics.py`.

---

## Failure Mode 1: High Error Rate

**Alert condition:**
```promql
rate(l9_errors_total[5m]) > 0.05
```

**Symptom:** Grafana dashboard shows error rate spike; `/v1/health` may return `degraded` or `unhealthy`.

**Immediate action:**
1. Check error breakdown by type:
   ```bash
   curl -s 'http://localhost:9091/api/v1/query?query=rate(l9_errors_total[5m])' | jq '.data.result[] | {error_type: .metric.error_type, rate: .value[1]}'
   ```
2. Check application logs for stack traces:
   ```bash
   docker compose logs -f --tail=100 app
   ```
3. Verify dependency health:
   ```bash
   curl http://localhost:8000/v1/health | python3 -m json.tool
   ```

**Root cause query:**
```promql
topk(5, sum by (error_type, component) (rate(l9_errors_total[5m])))
```

**Escalation:** If error rate > 0.1 rps for 10+ minutes, page on-call. If error_type is `Neo4jError` or `RedisError`, escalate to infrastructure team.

---

## Failure Mode 2: Neo4j Query Latency Spike

**Alert condition:**
```promql
histogram_quantile(0.95, rate(l9_neo4j_query_duration_seconds_bucket[5m])) > 2.0
```

**Symptom:** Grafana "Neo4j Query Latency" panel shows p95 > 2s; requests slow down; possible timeout errors.

**Immediate action:**
1. Verify Neo4j is responsive:
   ```bash
   curl http://localhost:8000/v1/health | jq '.checks.neo4j'
   ```
2. Check if specific query type is slow:
   ```bash
   curl -s 'http://localhost:9091/api/v1/query?query=histogram_quantile(0.95,rate(l9_neo4j_query_duration_seconds_bucket[5m]))' | jq '.data.result[] | {query_type: .metric.query_type, p95: .value[1]}'
   ```
3. Check Neo4j container resource usage:
   ```bash
   docker stats neo4j --no-stream
   ```

**Root cause query:**
```promql
topk(3, avg by (query_type) (rate(l9_neo4j_query_duration_seconds_sum[5m]) / rate(l9_neo4j_query_duration_seconds_count[5m])))
```

**Escalation:** If p95 > 5s for 10+ minutes and health check shows `error`, restart Neo4j container:
```bash
docker compose restart neo4j
```
If issue persists, escalate to database team.

---

## Failure Mode 3: Redis Latency Spike

**Alert condition:**
```promql
histogram_quantile(0.95, rate(l9_redis_op_duration_seconds_bucket[5m])) > 0.1
```

**Symptom:** Grafana "Redis Operation Latency" panel shows p95 > 100ms; cache performance degraded.

**Immediate action:**
1. Verify Redis is responsive:
   ```bash
   curl http://localhost:8000/v1/health | jq '.checks.redis'
   ```
2. Check Redis memory usage:
   ```bash
   docker exec redis redis-cli INFO memory | grep used_memory_human
   ```
3. Check slow log:
   ```bash
   docker exec redis redis-cli SLOWLOG GET 10
   ```

**Root cause query:**
```promql
topk(5, sum by (operation) (rate(l9_redis_op_duration_seconds_sum[5m]) / rate(l9_redis_op_duration_seconds_count[5m])))
```

**Escalation:** If Redis memory > 80% of limit, consider increasing memory limit or enabling eviction policy. If p95 > 500ms, restart Redis:
```bash
docker compose restart redis
```

---

## Failure Mode 4: Health Endpoint Returning 503

**Alert condition:**
```promql
up{job="enrichment-engine"} == 0
```
or health check probe fails in Prometheus targets page.

**Symptom:** `/v1/health` returns HTTP 503; Grafana shows "unhealthy" status.

**Immediate action:**
1. Check health response:
   ```bash
   curl -v http://localhost:8000/v1/health
   ```
2. Identify which dependency check failed:
   ```bash
   curl http://localhost:8000/v1/health | jq '.checks | to_entries[] | select(.value.status == "error")'
   ```
3. Check application container status:
   ```bash
   docker compose ps app
   ```

**Root cause:** Status is `unhealthy` only when Neo4j check fails. Verify Neo4j:
```bash
docker compose logs neo4j --tail=50
```

**Escalation:** If Neo4j container is down, restart:
```bash
docker compose up -d neo4j
```
If container is up but unresponsive, check Neo4j logs for database corruption or disk full.

---

## Failure Mode 5: Active Requests Saturating

**Alert condition:**
```promql
l9_http_requests_active > 50
```

**Symptom:** Active requests gauge stays high; requests queue up; latency increases.

**Immediate action:**
1. Check current active request count:
   ```bash
   curl -s http://localhost:8000/metrics | grep l9_http_requests_active
   ```
2. Check if a specific endpoint is slow:
   ```bash
   curl -s 'http://localhost:9091/api/v1/query?query=rate(l9_http_request_duration_seconds_count[1m])' | jq '.data.result[] | {endpoint: .metric.endpoint, rps: .value[1]}'
   ```
3. Verify worker/thread pool settings (uvicorn workers):
   ```bash
   ps aux | grep uvicorn
   ```

**Root cause query:**
```promql
rate(l9_http_request_duration_seconds_sum[5m]) / rate(l9_http_request_duration_seconds_count[5m])
```

**Escalation:** If active requests > 100 for 5+ minutes, consider:
- Increasing uvicorn workers: `uvicorn app.main:app --workers 4`
- Horizontal scaling (add more app containers)
- Circuit breaker activation if downstream dependency is slow

---

## Failure Mode 6: App Process Not Responding

**Alert condition:**
```promql
up{job="enrichment-engine"} == 0
```

**Symptom:** Prometheus targets page shows `DOWN`; no metrics scraped; application unreachable.

**Immediate action:**
1. Check if app container is running:
   ```bash
   docker compose ps app
   ```
2. Check app logs:
   ```bash
   docker compose logs app --tail=100
   ```
3. Verify port binding:
   ```bash
   curl http://localhost:8000/metrics
   ```

**Root cause:** Most common causes:
- App container crashed (OOM, unhandled exception at startup)
- Port 8000 already in use by another process
- Dependency (Neo4j, Redis) unavailable at startup causing crash

**Escalation:** Restart app container:
```bash
docker compose restart app
```
If crash persists, check:
```bash
docker inspect app
docker compose logs app --tail=500
```
Look for `exit code` in inspect output. Code 137 = OOM killed.

---

## Quick Reference: Prometheus Queries

All queries verified against `app/observability/metrics.py` schema.

| Metric | Query | Purpose |
|---|---|---|
| RPS | `rate(l9_http_requests_total[1m])` | Current request rate |
| Error % | `100 * (rate(l9_errors_total[1m]) / rate(l9_http_requests_total[1m]))` | Error percentage |
| p95 latency | `histogram_quantile(0.95, rate(l9_http_request_duration_seconds_bucket[5m]))` | 95th percentile response time |
| Active | `l9_http_requests_active` | In-flight requests |
| Neo4j p95 | `histogram_quantile(0.95, rate(l9_neo4j_query_duration_seconds_bucket[5m]))` | Neo4j query latency |
| Redis p95 | `histogram_quantile(0.95, rate(l9_redis_op_duration_seconds_bucket[5m]))` | Redis operation latency |

---

## Makefile Quick Actions

```bash
# Check if metrics endpoint is responding
make metrics-check

# Check health endpoint
make health-check

# Start monitoring stack
make monitoring-up

# Stop monitoring stack
make monitoring-down

# Follow monitoring logs
make monitoring-logs
```

---

## Contact

- **On-call rotation:** PagerDuty schedule `platform-team-l9`
- **Slack:** `#platform-alerts`
- **Escalation:** Infrastructure team for Neo4j/Redis issues; Platform team for app issues
