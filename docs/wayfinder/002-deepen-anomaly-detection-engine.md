# 002 - Deepen AnomalyDetectionEngine Architecture

**Label**: `wayfinder:grilling`
**Status**: `open`
**Assignee**: `unassigned`
**Blocked by**: None

## Question

How should `AnomalyDetectionEngine` encapsulate rolling statistical baselines, feature normalization, Isolation Forest ML modeling, and severity scoring behind a clean, deep interface?

Specifically:
1. What is the single narrow entry point for running anomaly detection on `DailySpendMetric` and `PaymentGatewayLog` data streams?
2. How do we eliminate redundant adapter conversions and pass-through helper functions so that complexity is concentrated rather than spread across files?
3. How will we test the engine end-to-end against known anomalous financial patterns (spikes, latency drifts, gateway timeouts)?
