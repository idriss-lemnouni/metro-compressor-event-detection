# Career summary

**FR**

- Développement d’un banc d’essai événementiel sur 1 516 948 relevés réels de compresseur MetroPT‑3.
- Évaluation chronologique d’un détecteur robuste par régime, avec 4 incidents appariés sur 4 et 17 alertes hors des fenêtres annotées.

**EN**

- Built a chronological compressor-event benchmark over 1,516,948 MetroPT-3 telemetry observations.
- Compared a pressure baseline with a regime-aware detector and audited incident matches, alert lead time and coverage gaps.

## Demonstrated skills

Streaming ETL, robust statistics, temporal anomaly detection, event evaluation and reporting of data coverage.

## Interview questions

- Why does a pointwise classification score hide the alert burden?
- How do missing windows affect three-in-a-row rules?
- What is the difference between incident matching and anticipation?
- Why calibrate the alert budget in a previous month?

## Two-minute explanation

Read the UCI data in one pass and measure its cadence. Build right-edge windows from observed pressure, temperature and motor current. Compare a low-pressure rule with robust regime-dependent distances. Learn centers and scales in February, choose a threshold based on March alarm burden, and evaluate on four documented holdout incidents. The robust detector matched all four and triggered before one.

## Five-minute explanation

1. Describe the compressor APU, the six sensors and the measured sampling gaps.
2. Show how the loaded regime changes the expected pressure and how median/MAD fits short windows.
3. Walk through the threshold choice, gap reset and cooldown with the unit tests.
4. Compare lead times and unmatched alerts per scorable day. Discuss the one early alert and the three other detections at or after onset.
5. Explain how uncertain annotations, limited event count and one vehicle constrain any deployment claim.

## Follow-up experiments

Replicate on another compressor, assess threshold stability by month and compare to an isolation-based detector using exactly the same event protocol.
