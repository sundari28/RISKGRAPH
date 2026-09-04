# RISKGRAPH — AI-Powered Financial Risk Intelligence

RISKGRAPH is an AI-powered financial risk intelligence platform built for the **Razorpay Buildathon — AI Risk Manager** track.

Instead of treating risk detection as a black-box prediction, RISKGRAPH follows an explainable investigation workflow:

**Detect → Cluster → Score → Explain → Investigate → Route**

## 🚀 What RISKGRAPH Does

RISKGRAPH analyzes transaction and customer relationships to identify coordinated risk patterns.

It:

* Builds a relationship graph across customers, transactions and shared identifiers
* Detects suspicious customer clusters
* Calculates risk scores and risk bands
* Extracts supporting behavioral signals
* Generates evidence-backed investigation summaries
* Identifies benign alternatives and uncertainty
* Routes cases to priority review or monitoring

## 🧠 Risk Intelligence Pipeline

```text
Transaction Data
       ↓
Graph Construction
       ↓
Candidate Cluster Detection
       ↓
Risk Signal Extraction
       ↓
Risk Scoring
       ↓
Policy Routing
       ↓
Evidence Packet
       ↓
Investigation
       ↓
Human Review / Monitoring
```

## 📊 Current Demo

The deployed system successfully processes the development dataset with:

* **15,119 graph nodes**
* **61,053 graph edges**
* **10 candidate risk clusters**
* **5 priority-review cases**
* **5 monitor-only cases**

The system exposes both analysis and investigation APIs through FastAPI and provides a web-based frontend for interactive investigation.

## 🏗️ Architecture

### Frontend

* React
* Vite
* Interactive risk-cluster investigation UI

### Backend

* Python
* FastAPI
* NetworkX
* Rule/policy-based risk routing
* Evidence generation and investigation pipeline

### Core Flow

```text
React Frontend
      ↓
FastAPI
      ↓
Graph Analysis Pipeline
      ↓
Risk Scoring
      ↓
Policy Engine
      ↓
Evidence + Investigation
```

## 🔍 Explainable Risk Detection

Each detected cluster can be investigated using observable evidence such as:

* Shared identifiers
* Temporal activity bursts
* Short refund timing
* Merchant fan-out
* Customer/transaction relationships

The system does not rely only on a final risk score. It provides evidence and uncertainty so that human reviewers can understand **why a case was flagged**.

## 🛡️ Human-in-the-Loop

RISKGRAPH is designed as a **decision-support system**, not an autonomous enforcement system.

High-risk cases are routed for priority review while lower-risk cases can be monitored.

This helps reduce the impact of false positives while keeping final decisions with human reviewers.

## 🌐 Live Demo

**Frontend:** https://riskgraph-giqr.onrender.com

**Backend API:** https://riskgraph-api.onrender.com

**API Documentation:** https://riskgraph-api.onrender.com/docs

## 📁 Project Structure

```text
RISKGRAPH/
├── app/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── data_generation/
│   │   ├── graph_analysis/
│   │   ├── investigation/
│   │   ├── policy/
│   │   └── risk_scoring/
│   ├── data/
│   ├── Dockerfile
│   └── requirements.txt
├── data/
├── docs/
├── frontend/
└── tests/
```

## 🎯 Buildathon Positioning

RISKGRAPH addresses the **AI Risk Manager** problem by combining graph-based detection with explainable investigation and human review routing.

The key design principle is:

> **Don't just flag risk. Show the connected evidence behind it.**

## ⚠️ Defense-Only System

RISKGRAPH is designed strictly for defensive financial-risk analysis, investigation and human review. It does not facilitate fraud, evasion or financial abuse.
