
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.graph_analysis.pipeline import analyze_dataset
from app.risk_scoring.scorer import score_clusters
from app.policy.policy import PolicyInput, evaluate_policy
from app.investigation.evidence import build_evidence_packet
from app.investigation.investigator import investigate
from app.investigation.schemas import EvidenceItem

from app.api.schemas import (
    AnalysisRunRequest,
    AnalysisRunResponse,
    HealthResponse,
    RootResponse,
    InvestigationResponseModel,
)


app = FastAPI(
    title="RISKGRAPH API",
    description="AI-powered financial risk intelligence system",
    version="1.0.0",
)

# Allow the deployed frontend to communicate with the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


DATA_DIR = Path(__file__).resolve().parents[2] / "data"


@app.get("/", response_model=RootResponse)
def root():
    return {
        "name": "RISKGRAPH",
        "status": "running",
        "version": "1.0.0",
    }


@app.get("/health", response_model=HealthResponse)
def health():
    return {"status": "healthy"}


def _run_analysis(split: str):
    graph_result = analyze_dataset(DATA_DIR, split)
    assessments = score_clusters(graph_result.clusters)

    policy_results = []

    for cluster, assessment in zip(
        graph_result.clusters,
        assessments,
    ):
        signals = cluster.signals

        established_legitimacy = (
            cluster.classification
            == "benign_shared_infrastructure_candidate"
        )

        policy_input = PolicyInput(
            risk_score=assessment.score,
            classification=cluster.classification,
            shared_identifier_types=signals.shared_identifier_type_count,
            temporal_burst_present=signals.temporal_burst_present,
            short_refund_count=signals.short_refund_count,
            behaviour_novelty_present=False,
            established_legitimacy=established_legitimacy,
        )

        policy_results.append(evaluate_policy(policy_input))

    return graph_result, assessments, policy_results


@app.post("/analyze", response_model=AnalysisRunResponse)
def analyze(request: AnalysisRunRequest):
    split = request.split.lower()

    if split == "development":
        split = "dev"

    if split not in {"dev", "test"}:
        raise HTTPException(
            status_code=400,
            detail="split must be 'dev' or 'test'",
        )

    try:
        graph_result, assessments, policy_results = _run_analysis(split)

        routing_counts = {
            "priority_review": 0,
            "investigate": 0,
            "monitor_only": 0,
        }

        for result in policy_results:
            routing_counts[result.routing] = (
                routing_counts.get(result.routing, 0) + 1
            )

        return AnalysisRunResponse(
            run_id=f"{split}-analysis",
            split=split,
            status="completed",
            candidate_cluster_count=graph_result.candidate_cluster_count,
            summary={
                "graph_nodes": graph_result.full_graph_node_count,
                "graph_edges": graph_result.full_graph_edge_count,
                "priority_review": routing_counts["priority_review"],
                "investigate": routing_counts["investigate"],
                "monitor_only": routing_counts["monitor_only"],
            },
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {exc}",
        ) from exc


@app.get(
    "/investigate/{cluster_id}",
    response_model=InvestigationResponseModel,
)
def investigate_cluster(cluster_id: str, split: str = "dev"):
    split = split.lower()

    if split == "development":
        split = "dev"

    if split not in {"dev", "test"}:
        raise HTTPException(
            status_code=400,
            detail="split must be 'dev' or 'test'",
        )

    try:
        graph_result, assessments, policy_results = _run_analysis(split)

        for cluster, assessment, policy_result in zip(
            graph_result.clusters,
            assessments,
            policy_results,
        ):
            if cluster.cluster_id != cluster_id:
                continue

            evidence = []

            signals = cluster.signals

            if signals.shared_identifier_type_count > 0:
                evidence.append(
                    EvidenceItem(
                        evidence_id="EV-001",
                        category="shared_identifier",
                        description=(
                            f"{signals.shared_identifier_type_count} "
                            "types of shared identifiers connect customers."
                        ),
                        entity_ids=tuple(cluster.member_customer_ids),
                    )
                )

            if signals.temporal_burst_present:
                evidence.append(
                    EvidenceItem(
                        evidence_id="EV-002",
                        category="temporal_burst",
                        description=(
                            "Concentrated activity was detected across "
                            f"{signals.peak_window_customer_count} customers."
                        ),
                        entity_ids=tuple(cluster.member_customer_ids),
                    )
                )

            if signals.short_refund_count > 0:
                evidence.append(
                    EvidenceItem(
                        evidence_id="EV-003",
                        category="refund_anomaly",
                        description=(
                            f"{signals.short_refund_count} refunds "
                            "occurred with short refund timing."
                        ),
                        entity_ids=tuple(cluster.member_customer_ids),
                    )
                )

            if signals.merchant_fanout_count > 0:
                evidence.append(
                    EvidenceItem(
                        evidence_id="EV-004",
                        category="merchant_fanout",
                        description=(
                            f"Activity spans {signals.merchant_fanout_count} "
                            "distinct merchants."
                        ),
                        entity_ids=tuple(cluster.member_customer_ids),
                    )
                )

            packet = build_evidence_packet(
                case_id=cluster.cluster_id,
                analysis_run_id=f"{split}-analysis",
                risk_score=assessment.score,
                risk_band=assessment.band,
                policy_result=policy_result.routing,
                evidence=evidence,
            )

            result = investigate(packet)

            return InvestigationResponseModel(
                case_id=cluster.cluster_id,
                summary=result.summary,
                observed_evidence=list(result.observed_evidence),
                benign_alternatives=list(result.benign_alternatives),
                uncertainty=list(result.uncertainty),
                review_questions=list(result.review_questions),
                recommendation=result.recommendation,
                cited_evidence_ids=list(result.cited_evidence_ids),
            )

        raise HTTPException(
            status_code=404,
            detail=f"Cluster '{cluster_id}' not found",
        )

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Investigation failed: {exc}",
        ) from exc


@app.get("/clusters")
def get_clusters(split: str = "dev"):
    split = split.lower()

    if split == "development":
        split = "dev"

    if split not in {"dev", "test"}:
        raise HTTPException(
            status_code=400,
            detail="split must be 'dev' or 'test'",
        )

    try:
        graph_result, assessments, policy_results = _run_analysis(split)

        clusters = []

        for cluster, assessment, policy_result in zip(
            graph_result.clusters,
            assessments,
            policy_results,
        ):
            clusters.append(
                {
                    "cluster_id": cluster.cluster_id,
                    "classification": cluster.classification,
                    "risk_score": assessment.score,
                    "risk_band": assessment.band,
                    "routing": policy_result.routing,
                    "member_customer_count": len(
                        cluster.member_customer_ids
                    ),
                    "transaction_count": len(
                        cluster.transaction_ids
                    ),
                    "shared_identifier_types": (
                        cluster.signals.shared_identifier_type_count
                    ),
                    "temporal_burst": (
                        cluster.signals.temporal_burst_present
                    ),
                    "short_refund_count": (
                        cluster.signals.short_refund_count
                    ),
                    "merchant_fanout_count": (
                        cluster.signals.merchant_fanout_count
                    ),
                }
            )

        return {
            "split": split,
            "clusters": clusters,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Cluster retrieval failed: {exc}",
        ) from exc
    
