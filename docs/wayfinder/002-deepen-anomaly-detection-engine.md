# 002 - Deepen AnomalyDetectionEngine Architecture

**Label**: `wayfinder:grilling`
**Status**: `closed`
**Assignee**: `Antigravity`
**Blocked by**: None

## Question

How should `AnomalyDetectionEngine` encapsulate rolling statistical baselines, feature normalization, Isolation Forest ML modeling, and severity scoring behind a clean, deep interface?

Specifically:
1. What is the single narrow entry point for running anomaly detection on `DailySpendMetric` and `PaymentGatewayLog` data streams?
2. How do we eliminate redundant adapter conversions and pass-through helper functions so that complexity is concentrated rather than spread across files?
3. How will we test the engine end-to-end against known anomalous financial patterns (spikes, latency drifts, gateway timeouts)?

## Resolution

1. **Generalized Deep Interface**:
   - `AnomalyDetectionEngine` provides a simple, generalized entry point that dynamically detects anomalies across any numeric metric streams without rigid dataset-specific lock-in:
     - `scan_dataframe(df: pd.DataFrame, fill_calendar_gaps: bool = True) -> list[AnomalySignal]`
     - `async scan_and_persist(dataset_source: str = "FINTECH_90D", session: AsyncSession | None = None) -> list[AnomalyEvent]`
2. **Dynamic Ensemble & Continuous Time-Series Gap Filling**:
   - Dynamically scans available numeric metrics (e.g., latency, error rate, success rate, chargeback %, transaction volume) and computes rolling Z-scores combined with an Isolation Forest multi-metric anomaly detector.
   - Automatically fills calendar gaps per partition slice so rolling windows reflect true elapsed calendar time without division-by-zero or jagged time-series voids.
   - Simple, standardized composite severity grading (`CRITICAL`, `HIGH`, `MEDIUM`).
3. **Atomic Deduplication & Persistence**:
   - `scan_and_persist` checks existing `(detected_at, region, product_name, customer_tier, metric_name, dataset_source)` keys in a single query, inserting only new unique anomaly events.
4. **Black-box Test Surface**:
   - `tests/test_anomaly_detector.py` tests detection against injected latency surges, chargeback spikes, sparse-date gap filling, and database deduplication.
