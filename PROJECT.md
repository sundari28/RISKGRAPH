# RISKGRAPH

## Project

RISKGRAPH is an AI-powered financial risk intelligence system for detecting coordinated abuse patterns across customers, transactions, devices, IP addresses, refunds, merchants and related entities.

## Buildathon Track

Razorpay AI Buildathon — Track 02: AI Risk Manager.

## Core Problem

Traditional transaction-level fraud detection can miss coordinated abuse because individual transactions may appear legitimate while relationships between accounts reveal a larger suspicious pattern.

RISKGRAPH analyzes these relationships as a graph and produces an explainable risk assessment.

## Core Workflow

Transaction Data
→ Data Normalization
→ Relationship Graph
→ Risk Signal Detection
→ Suspicious Cluster Detection
→ Risk Scoring
→ AI Investigation
→ Evidence-Based Explanation
→ Policy Recommendation
→ Audit Trail
→ Evaluation

## Core Principles

1. Risk detection must be explainable.
2. AI must not independently make irreversible financial decisions.
3. Risk scores must be based on observable evidence.
4. AI should explain structured evidence rather than invent evidence.
5. The system must be evaluated on a held-out test set.
6. False positives must be measured.
7. Legitimate high-value customers must not automatically be treated as fraudulent.
8. Every recommendation should have an auditable reason.

## Initial MVP

The first version must:

* Generate realistic synthetic payment-risk data.
* Create relationships between customers, devices, IPs, transactions and refunds.
* Detect suspicious clusters.
* Calculate an interpretable risk score.
* Display the suspicious cluster visually.
* Explain the evidence behind the risk score.
* Produce evaluation metrics on a held-out dataset.

## Later Features

After the MVP works:

* AI investigator
* policy engine
* human-review workflow
* audit trail
* Razorpay test-mode integration
* risk simulation
* polished dashboard
* deployment

## Important Constraint

Do not build a generic chatbot or a simple binary fraud classifier.

The differentiating feature is coordinated abuse detection through relationships between entities.

