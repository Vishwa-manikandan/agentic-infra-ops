"""
Toy service for the Agentic Infra-Ops project (Phase 1).

Simulates a small web service under load:
- Normal traffic with realistic latency distribution
- Periodic "incidents" where error rate and latency spike
  (this is what the Phase 3 LangGraph agent will later detect)

Exposes:
  GET /work      -> simulated endpoint, randomly succeeds/fails
  GET /health    -> liveness probe
  GET /metrics   -> Prometheus scrape target
"""

import random
import time
import threading
import logging
import json
import sys

from fastapi import FastAPI, Response
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    generate_latest,
    CONTENT_TYPE_LATEST,
)

# Configure structured JSON logging to stdout
class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "funcName": record.funcName,
            "lineno": record.lineno,
        }
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_record)

logger = logging.getLogger("toy-service")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JsonFormatter())
logger.addHandler(handler)

app = FastAPI(title="toy-service")

# --- Metrics -----------------------------------------------------------

REQUEST_COUNT = Counter(
    "toy_service_requests_total",
    "Total requests handled",
    ["endpoint", "status"],
)

REQUEST_LATENCY = Histogram(
    "toy_service_request_duration_seconds",
    "Request latency in seconds",
    ["endpoint"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)

INCIDENT_MODE = Gauge(
    "toy_service_incident_mode",
    "1 if the service is currently simulating a degraded state, else 0",
)

# --- Background traffic / incident simulator ----------------------------

_incident_active = False


def _incident_loop():
    """Flips the service into a degraded state every ~90s for ~20s,
    so there's something real for Prometheus/Grafana (and later, the
    agent) to detect."""
    global _incident_active
    while True:
        time.sleep(90)
        _incident_active = True
        INCIDENT_MODE.set(1)
        time.sleep(20)
        _incident_active = False
        INCIDENT_MODE.set(0)


def _background_traffic():
    """Generates continuous synthetic requests so the dashboard has
    live data without the user needing to hit the API manually."""
    while True:
        _simulate_request("background")
        time.sleep(random.uniform(0.05, 0.3))


def _simulate_request(endpoint: str) -> tuple[int, float]:
    base_latency = random.uniform(0.02, 0.15)
    fail_probability = 0.02

    if _incident_active:
        base_latency += random.uniform(0.5, 2.5)
        fail_probability = 0.35

    start = time.time()
    time.sleep(min(base_latency, 0.05))  # don't actually block long in-process
    duration = time.time() - start + base_latency  # recorded duration reflects simulated latency

    failed = random.random() < fail_probability
    status = "500" if failed else "200"

    if failed:
        logger.error(f"Request failed with status {status}", extra={"endpoint": endpoint, "duration": duration})
    else:
        logger.info(f"Request succeeded with status {status}", extra={"endpoint": endpoint, "duration": duration})

    REQUEST_COUNT.labels(endpoint=endpoint, status=status).inc()
    REQUEST_LATENCY.labels(endpoint=endpoint).observe(duration)

    return (500 if failed else 200), duration


@app.get("/work")
def work():
    status, duration = _simulate_request("work")
    return {"status": status, "duration_ms": round(duration * 1000, 2)}


@app.get("/health")
def health():
    return {"status": "ok", "incident_mode": _incident_active}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.on_event("startup")
def start_background_threads():
    threading.Thread(target=_background_traffic, daemon=True).start()
    threading.Thread(target=_incident_loop, daemon=True).start()
