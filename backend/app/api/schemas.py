from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str


class RootResponse(BaseModel):
    name: str
    status: str
    version: str


class AnalysisRunRequest(BaseModel):
    split: str = Field(default="development")
    start_time: str | None = None
    end_time: str | None = None


class AnalysisRunResponse(BaseModel):
    run_id: str
    split: str
    status: str
    candidate_cluster_count: int = 0
    summary: dict[str, Any] = Field(default_factory=dict)


class ClusterSummary(BaseModel):
    cluster_id: str
    classification: str
    risk_score: float | None = None
    member_customer_count: int
    transaction_count: int


class InvestigationResponseModel(BaseModel):
    case_id: str
    summary: str
    observed_evidence: list[str]
    benign_alternatives: list[str]
    uncertainty: list[str]
    review_questions: list[str]
    recommendation: str
    cited_evidence_ids: list[str]