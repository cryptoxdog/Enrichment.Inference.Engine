"""
Load test harness for ENRICH service.
Run: locust -f tests/load/locustfile.py --host http://localhost:8000 --users 100 --spawn-rate 10
"""

import random

from locust import HttpUser, between, task

DOMAINS = ["plasticos"]
MATERIALS = ["HDPE", "LDPE", "PP", "PET"]


class EnrichUser(HttpUser):
    wait_time = between(0.5, 2)

    @task(3)
    def enrich_entity(self):
        self.client.post(
            "/enrich",
            json={
                "entity_id": f"load-test-{random.randint(1, 10_000)}",
                "entity_type": "facility",
                "domain": random.choice(DOMAINS),
                "fields": {
                    "company_name": "Load Test Co",
                    "materials_handled": random.sample(MATERIALS, 2),
                },
            },
            headers={"Authorization": "Bearer load-test-key"},
        )

    @task(1)
    def scan_fields(self):
        self.client.post(
            "/v1/scan",
            json={
                "crm_fields": [
                    {"name": "company_name", "type": "string"},
                    {"name": "materials_handled", "type": "list"},
                ],
                "domain": "plasticos",
            },
            headers={"Authorization": "Bearer load-test-key"},
        )

    @task(1)
    def health_check(self):
        self.client.get("/v1/health")
