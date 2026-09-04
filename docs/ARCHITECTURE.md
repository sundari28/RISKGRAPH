# RISKGRAPH Architecture

## Purpose and MVP Boundary

RISKGRAPH is a single, hackathon-grade risk-intelligence application for finding coordinated payment abuse that is difficult to see in isolated transactions. It analyzes a relationship graph spanning customers, merchants, transactions, devices, IP addresses, addresses, and refunds.

The MVP is a modular monolith: one Next.js frontend, one FastAPI backend, and one PostgreSQL database. NetworkX performs in-process graph analysis over a bounded dataset. This keeps the system easy to build, inspect, test, and demonstrate without introducing distributed infrastructure.

### Decision boundary

The system does **not** declare a customer or transaction fraudulent. Deterministic graph and transaction signals produce a risk score and a suggested review priority. The AI Investigator is strictly downstream: it receives only structured, retrieved evidence and produces a grounded explanation for a human reviewer. Policy rules can route a case to review or mark it as monitor-only; final action remains human-controlled.

## Goals and Non-Goals

Goals:

- Detect coordinated abuse through shared entities and suspicious graph structure.
- Separate suspicious coordination from legitimate high-value activity using behavioural and relationship evidence.
- Make each score reproducible from observable inputs and versioned rules.
- Demonstrate measurable results on a held-out, labelled synthetic dataset.
- Preserve an auditable record of scoring, AI explanations, policy decisions, and reviewer actions.

Non-goals for the MVP:

- Automated blocking, refunding, account restriction, or fraud adjudication.
- Real-time stream processing or high-volume production scaling.
- A generic chatbot, opaque binary classifier, or autonomous agent.
- LangChain, vector databases, Kafka, Redis, Kubernetes, microservices, or complex cloud infrastructure.

## System Overview

```text
Synthetic dataset (labelled) ──> PostgreSQL ──> FastAPI analysis service
                                      │              │
                                      │              ├─ normalizes records
                                      │              ├─ builds NetworkX graph
                                      │              ├─ detects clusters/signals
                                      │              ├─ calculates risk score
                                      │              ├─ applies guardrails
                                      │              └─ writes audit events
                                      │
Next.js dashboard <──────────── REST API ────────────┘
      │
      └─ reviewer requests investigation
                    │
                    └─ AI Investigator receives structured evidence only
                                      │
                                      └─ explanation + cited evidence IDs
```

The backend exposes REST endpoints and owns all business logic. The frontend renders dashboards, graph views, explanations, metrics, and review queues; it never calculates a risk decision. PostgreSQL is the durable source of truth. NetworkX graphs are built from a selected analysis window and are not stored as the authoritative database.

## Components

### Frontend: Next.js, TypeScript, Tailwind CSS, and shadcn/ui

The frontend is a Next.js TypeScript application using Tailwind CSS and shadcn/ui for accessible, consistent interface primitives. It calls the FastAPI REST API and contains no direct database access or scoring logic.

Core screens for the MVP:

- **Overview:** dataset run status, high-risk clusters, review-queue counts, and held-out evaluation results.
- **Cluster investigation:** graph visualization with node types, relationship edges, cluster signals, linked transactions, and score breakdown.
- **Case review:** structured evidence, AI Investigator explanation, policy recommendation, reviewer decision, and comment fields.
- **Evaluation:** precision, recall, F1, false-positive cost, confusion matrix, and threshold comparison for the held-out dataset.

The graph view should make relationships legible rather than act as a generic graph browser: show a small cluster-focused subgraph, colour node type, label important links, and allow evidence drill-down.

### Backend: Python and FastAPI

FastAPI runs as one deployable backend process with clear modules for ingestion, normalization, graph construction, detection, scoring, investigation, policy, auditing, and evaluation. It validates requests and responses with Pydantic models, centralizes authentication/authorization hooks, and serves OpenAPI documentation for integration and demo use.

An analysis run is explicit and repeatable: select a dataset version and time window, construct the graph, calculate findings, persist results, and expose the immutable run ID. Small hackathon datasets can be processed synchronously or through a simple in-process background task; status remains queryable. No separate worker, queue, or scheduler is required.

### PostgreSQL data layer

PostgreSQL stores normalized source records, synthetic labels, analysis results, cases, audit events, and evaluation outputs. Database constraints, foreign keys, timestamps, and immutable run/version identifiers support reliable joins and reproducibility.

Suggested logical tables:

| Area | Records |
| --- | --- |
| Core entities | `customers`, `merchants`, `devices`, `ip_addresses`, `addresses` |
| Payments | `transactions`, `refunds` |
| Provenance | `dataset_versions`, `analysis_runs`, source-row metadata |
| Analysis | `clusters`, `cluster_members`, `risk_assessments`, `risk_signals`, `evidence_items` |
| Review and governance | `review_cases`, `review_decisions`, `policy_evaluations`, `audit_events` |
| Evaluation | `evaluation_runs`, aggregate metrics, per-item predictions |

Sensitive fields should be minimized. Store stable, salted hashes for device identifiers and IP/address fingerprints in demo data where possible, avoid secrets and payment-card data entirely, and keep synthetic raw inputs clearly marked as non-production data.

### NetworkX graph analysis

For each analysis run, the backend builds a typed graph in memory. Nodes represent `customer`, `merchant`, `transaction`, `device`, `ip_address`, `address`, and `refund`. Edges represent observable relationships and carry timestamps and identifiers, for example:

- customer → transaction; transaction → merchant
- transaction → device; transaction → IP address; customer → address
- refund → original transaction
- customer → device/IP/address when derived from a transaction

Edges retain enough metadata to explain every path shown to a reviewer. The graph construction is deterministic for a dataset version and analysis window. NetworkX is sufficient for the initial bounded synthetic corpus; analysis is rerun from PostgreSQL rather than depending on a persistent graph database.

## Data and Synthetic Scenario Design

The synthetic generator must produce a labelled development split and a held-out evaluation split with a fixed seed recorded in `dataset_versions`. It should create both normal and suspicious scenarios, with realistic timestamps, amounts, merchant categories, approvals, failures, refund timing, devices, IPs, and addresses.

Include at least these cohorts:

- Normal low and medium-value customers with mostly unique identity attributes.
- Legitimate high-value customers with stable device/IP/address patterns, longer account history, recurring merchant relationships, and expected refund behaviour.
- Coordinated-abuse rings that share devices, IPs, or addresses across otherwise distinct customers; fan out across merchants; produce bursty activity; and display anomalous refund or transaction patterns.
- Benign shared infrastructure cases, such as family/office/shared-network customers, to exercise false-positive controls.

Ground-truth labels are for evaluation only and must never be passed into the scoring or AI explanation path. The generator records scenario type and source seed so test failures can be reproduced.

## Detection and Interpretable Risk Scoring

### Candidate-cluster detection

The initial implementation should favour clear, testable algorithms over sophisticated community detection. Build candidate clusters from connected components in a projected entity graph, then flag components that satisfy configurable coordination criteria. A component may be suspicious when it contains multiple distinct customers linked through one or more shared devices, IPs, or addresses and has supporting behavioural signals.

Useful observable features include:

- Count of distinct customers per device, IP, or address, normalized for known benign sharing.
- Number and density of shared-identifier paths connecting customers.
- Rapid transaction bursts across multiple accounts or merchants.
- Concentration of transactions through a small set of merchants or shared identifiers.
- Refund rate, refund amount ratio, and unusually short refund timing.
- Device/IP/address novelty and reuse relative to the customer’s history.
- Customer account age, historical behaviour consistency, and payment success/failure patterns.
- High transaction value only in context: it is a weak signal, offset by a stable history and absence of coordination evidence.

Clusters below a minimum evidence threshold are retained as low-confidence findings or ignored; a shared IP alone must not create a high-risk case.

### Score model

Risk is a deterministic weighted score from 0–100. Each signal produces a normalized contribution, a human-readable reason, supporting entity/transaction IDs, and the scoring-rule version. A practical initial model is:

```text
risk_score = clamp(0, 100,
  35 × coordination_strength
  + 20 × shared_identifier_risk
  + 15 × temporal_burst_risk
  + 15 × refund_anomaly_risk
  + 10 × behaviour_novelty_risk
  +  5 × transaction_value_context_risk
  - 20 × established_legitimacy_offset)
```

Weights and thresholds live in a versioned, reviewable ruleset. `established_legitimacy_offset` reflects stable long-term history, expected recurring activity, and benign explanations for shared infrastructure; it cannot erase strong coordinated-abuse evidence. Score bands are descriptive: for example, `0–39` monitor, `40–69` investigate, and `70–100` priority review. They are not fraud verdicts or automatic actions.

Each risk assessment stores the exact components and evidence IDs needed to recompute it. This makes the score unit-testable, reviewable, and suitable for threshold evaluation.

## AI Investigator

The AI Investigator is an explanation component, not a detector or decision-maker. The backend sends it a strictly structured evidence packet generated after scoring, containing:

- Cluster/case ID, analysis-run ID, score, score band, and policy result.
- Scoring signals with values, weights, and deterministic explanations.
- Relevant entities and concise relationship paths (for example, Customer A → Device X ← Customer B).
- Aggregated behavioural facts such as time ranges, counts, amount ranges, and refund statistics.
- Legitimate-context indicators and explicitly missing/uncertain evidence.
- A closed set of evidence IDs to cite.

The prompt requires a structured response with: summary, observed evidence, benign alternatives, uncertainty, recommended human-review questions, and a non-binding recommendation. It must state that the result is a risk assessment, not a fraud finding. The backend validates the response schema, verifies that cited evidence IDs are in the supplied packet, and rejects/repairs unsupported citations. The UI displays the deterministic score breakdown alongside the explanation so the model cannot become the source of truth.

If the model is unavailable, the case remains reviewable with deterministic evidence and a templated explanation. No AI output is required to calculate score, run policy, or preserve an audit trail.

## Policy and Guardrails

Policy is deterministic, versioned backend logic applied after scoring and before a case is presented for action. It determines routing, not fraud status.

Initial guardrails:

- Never permit autonomous account, payment, refund, or merchant action.
- Require a minimum number of independent evidence categories before priority review (for example, shared identifier plus burst/refund/novelty evidence).
- Treat value as contextual; high value alone cannot elevate a case above monitor-only.
- Down-rank or require more evidence for known benign shared-network patterns.
- Require human confirmation for every case outcome.
- Prevent AI text from changing score, evidence, policy result, or case status.
- Redact or hash sensitive identifiers in the frontend and AI evidence packet as appropriate.

Policy evaluation records both the input facts and the ruleset version, allowing reviewers to understand why a case was routed.

## Human Review Workflow

1. An analysis run creates risk assessments and policy evaluations.
2. Eligible findings create review cases with a priority and deterministic evidence snapshot.
3. A reviewer inspects the score components, graph paths, transaction/refund timeline, legitimate-context indicators, and AI explanation.
4. The reviewer records one outcome: `confirmed_concern`, `benign`, `needs_more_information`, or `dismissed`, plus an optional rationale.
5. The system writes an immutable audit event and preserves the original assessment; later rescoring creates a new version rather than overwriting the old one.

For the Buildathon demo, reviewer outcomes can be local application records. They must not trigger external payment actions.

## Audit Trail

Append-only `audit_events` capture who or what performed an action, when, the resource type and ID, action name, request/correlation ID, and sanitized before/after or reference payload. Audit events cover dataset generation, analysis execution, score creation, policy evaluation, AI request/response metadata, case creation, evidence access, and reviewer decisions.

Audit records should reference persisted evidence snapshots and model/ruleset versions. Avoid placing API keys, prompts containing sensitive raw data, or unredacted identifiers in audit payloads.

## API Boundaries

All API responses use typed Pydantic schemas and stable IDs. The frontend uses only these endpoints; internal graph and scoring functions remain private backend modules.

| Endpoint group | Responsibility |
| --- | --- |
| `POST /datasets/generate` | Create a seeded synthetic dataset version and report counts. |
| `GET /datasets` | List dataset versions and split metadata. |
| `POST /analysis-runs` | Start analysis for a dataset version/time window/ruleset. |
| `GET /analysis-runs/{id}` | Retrieve run status and summary. |
| `GET /clusters` / `GET /clusters/{id}` | List clusters and retrieve graph-ready nodes, edges, signals, and evidence. |
| `GET /risk-assessments/{id}` | Return score, components, score/ruleset version, and evidence references. |
| `POST /cases/{id}/investigate` | Generate or retrieve grounded AI explanation; never accept a score from AI. |
| `GET /cases` / `GET /cases/{id}` | Review queue and full review context. |
| `POST /cases/{id}/decisions` | Record an authenticated human decision and rationale. |
| `POST /evaluations` / `GET /evaluations/{id}` | Evaluate a ruleset/threshold on held-out data and return metrics. |
| `GET /audit-events` | Retrieve scoped audit history for authorized reviewers/admins. |

The MVP can use simple role-aware local authentication or demo identities, but authorization must distinguish at least viewer, reviewer, and admin roles. Production payment-provider integration is intentionally out of scope.

## Evaluation

Evaluation uses only the held-out synthetic split and compares deterministic system findings against its hidden ground-truth labels. Establish the prediction unit explicitly—initially, a cluster or linked customer group is positive when its risk score meets the selected review threshold.

Report:

- Precision: fraction of flagged findings that are truly coordinated-abuse findings.
- Recall: fraction of labelled coordinated-abuse findings detected.
- F1: harmonic balance of precision and recall.
- Confusion matrix: true/false positives and true/false negatives.
- False-positive cost: `false_positives × configured_review_cost`, with an optional additional weighted cost for benign high-value customers.
- Results by scenario cohort, especially legitimate high-value and benign shared-infrastructure cases.

Evaluation runs persist dataset, split, ruleset, threshold, seed, timestamp, and metrics so demonstrations are repeatable. Compare a small range of thresholds and choose one that meets the desired false-positive-cost trade-off; do not tune on the held-out split repeatedly without recording that decision.

## Testing Strategy

- **Unit tests:** normalization, graph edge construction, each risk signal, weights/score clamping, legitimacy offsets, policy guardrails, evidence-packet construction, and metric calculations.
- **Scenario tests:** known synthetic rings are detected; high-value stable customers are not escalated solely for value; a shared office/family IP alone does not trigger priority review; refund anomalies require supporting context.
- **Integration tests:** API to PostgreSQL flows for dataset generation, analysis run, case creation, human decision, audit events, and evaluation.
- **Contract tests:** FastAPI response schemas used by the frontend, including graph and AI-explanation structures.
- **AI safety tests:** mocked model outputs with invented evidence IDs, unsupported claims, malformed JSON, and unavailable-provider cases; verify safe fallback and no score mutation.
- **End-to-end smoke test:** generate a fixed-seed dataset, run analysis, open a cluster, request an investigation, submit a review decision, and retrieve metrics/audit history.

Use deterministic fixtures and fixed seeds in automated tests. Test data and labels must remain separate from the production scoring input path.

## Local Development Workflow

1. Start PostgreSQL locally (a single local instance or a developer-managed container is sufficient).
2. Configure local, non-secret development settings for the frontend and backend; keep real AI-provider credentials out of source control.
3. Run FastAPI locally with automatic reload and apply database migrations/seed a synthetic dataset.
4. Run the Next.js development server, pointing it to the local API.
5. Generate a fixed-seed development dataset, create an analysis run, inspect clusters and cases, then run held-out evaluation.
6. Run backend tests and frontend checks before demo packaging.

The backend should function without AI credentials, using the deterministic evidence view and explanation fallback. This keeps the core demo reliable.

## Deployment Approach

Deploy the frontend and backend as two simple services, with a managed PostgreSQL instance. A practical hackathon deployment is a Next.js host for the UI and a container-capable host for FastAPI, using environment variables for database connection, allowed frontend origin, authentication settings, and optional AI-provider key. Configure HTTPS, restrictive CORS, database backups, and health endpoints.

Run NetworkX analysis within the backend process against bounded demo data. If analysis becomes slow, first limit time windows and graph size or use a simple background task/status endpoint. A separate worker or distributed graph system is not justified for the MVP. Store generated datasets, analysis results, and audit records in PostgreSQL; do not depend on ephemeral process memory for durable results.

## Architecture Risks & Open Questions

- What exact coordinated-abuse patterns and labels best match the Buildathon judging criteria, and how should synthetic data reflect them?
- What entity scale and analysis-window size must the live demo support before in-process NetworkX becomes too slow?
- What review-cost assumptions should define false-positive cost, particularly for legitimate high-value customers?
- Which shared device/IP/address patterns should be treated as plausible benign infrastructure, and what evidence is sufficient to override that presumption?
- Will an AI-provider API be available during judging, and what model, cost, latency, rate-limit, and data-handling constraints apply?
- What identifier fields may be sent to the AI provider, even in synthetic/demo scenarios, and what redaction policy is required?
- What minimum authentication is expected for the demo versus any post-hackathon deployment?
- What threshold and score weights should be selected before evaluation, and how will changes be versioned to prevent accidental test-set tuning?
- Is cluster-level, customer-level, or transaction-level review the most useful unit for the judges and future operators?
- Does Razorpay test-mode integration become an explicit requirement later, and what event/data contract would it provide?
