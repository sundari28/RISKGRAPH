import { useState } from "react";
import "./App.css";

const API = "http://localhost:8000";

function App() {
  const [loading, setLoading] = useState(false);
  const [clustersLoading, setClustersLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [clusters, setClusters] = useState([]);
  const [investigation, setInvestigation] = useState(null);
  const [investigating, setInvestigating] = useState(false);
  const [error, setError] = useState("");

  const runAnalysis = async () => {
    setLoading(true);
    setClustersLoading(true);
    setError("");
    setInvestigation(null);

    try {
      const analysisResponse = await fetch(`${API}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ split: "dev" }),
      });

      if (!analysisResponse.ok) {
        throw new Error("Analysis request failed");
      }

      const analysisData = await analysisResponse.json();
      setResult(analysisData);

      const clustersResponse = await fetch(`${API}/clusters?split=dev`);

      if (!clustersResponse.ok) {
        throw new Error("Cluster request failed");
      }

      const clusterData = await clustersResponse.json();
      setClusters(clusterData.clusters || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
      setClustersLoading(false);
    }
  };

  const investigateCluster = async (clusterId) => {
    setInvestigating(true);
    setError("");

    try {
      const response = await fetch(
        `${API}/investigate/${clusterId}?split=dev`
      );

      if (!response.ok) {
        throw new Error("Investigation request failed");
      }

      const data = await response.json();
      setInvestigation(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setInvestigating(false);
    }
  };

  const routingClass = (routing) => {
    if (routing === "priority_review") return "priority";
    if (routing === "investigate") return "investigate";
    return "monitor";
  };

  const formatRouting = (routing = "") =>
    routing.replaceAll("_", " ");

  return (
    <div className="app">

      <header className="topbar">
        <div>
          <div className="logo">
            RISK<span>GRAPH</span>
          </div>
          <p>Financial Risk Intelligence</p>
        </div>

        <div className="system-status">
          <span></span>
          System Online
        </div>
      </header>

      <main>

        <section className="hero">
          <div>
            <div className="eyebrow">
              RISK INTELLIGENCE PLATFORM
            </div>

            <h1>
              Understand risk.
              <br />
              <span>Investigate with evidence.</span>
            </h1>

            <p>
              Detect coordinated financial activity, identify
              risk clusters and route cases for human review.
            </p>
          </div>

          <button
            className="run-button"
            onClick={runAnalysis}
            disabled={loading}
          >
            {loading ? "Analyzing..." : "Run Analysis →"}
          </button>
        </section>

        {error && (
          <div className="error">
            {error}
          </div>
        )}

        {!result && !loading && (
          <section className="empty">
            <div className="empty-symbol">◎</div>
            <h2>No analysis run yet</h2>
            <p>
              Run an analysis to generate the latest risk intelligence.
            </p>
          </section>
        )}

        {loading && (
          <section className="empty">
            <div className="spinner"></div>
            <h2>Analyzing transaction graph...</h2>
            <p>
              Building relationships, detecting clusters and calculating risk.
            </p>
          </section>
        )}

        {result && (
          <>

            <section className="section-title">
              <div>
                <div className="eyebrow">LATEST ANALYSIS</div>
                <h2>Development Analysis</h2>
              </div>

              <div className="completed">
                ● {result.status}
              </div>
            </section>

            <section className="stats">

              <div className="stat">
                <span>GRAPH NODES</span>
                <strong>
                  {result.summary.graph_nodes?.toLocaleString()}
                </strong>
              </div>

              <div className="stat">
                <span>GRAPH EDGES</span>
                <strong>
                  {result.summary.graph_edges?.toLocaleString()}
                </strong>
              </div>

              <div className="stat">
                <span>CANDIDATE CLUSTERS</span>
                <strong>
                  {result.candidate_cluster_count}
                </strong>
              </div>

              <div className="stat danger">
                <span>PRIORITY REVIEW</span>
                <strong>
                  {result.summary.priority_review}
                </strong>
              </div>

            </section>

            <section className="routing">

              <div className="route priority">
                <span>Priority Review</span>
                <strong>{result.summary.priority_review}</strong>
                <small>Immediate human review</small>
              </div>

              <div className="route investigate">
                <span>Investigate</span>
                <strong>{result.summary.investigate}</strong>
                <small>Additional investigation</small>
              </div>

              <div className="route monitor">
                <span>Monitor Only</span>
                <strong>{result.summary.monitor_only}</strong>
                <small>No elevated review required</small>
              </div>

            </section>

            <section className="clusters">

              <div className="section-title">
                <div>
                  <div className="eyebrow">
                    DETECTED CLUSTERS
                  </div>
                  <h2>Risk Clusters</h2>
                </div>

                <span className="count">
                  {clusters.length} detected
                </span>
              </div>

              {clustersLoading ? (
                <div className="loading-text">
                  Loading clusters...
                </div>
              ) : (

                <div className="cluster-grid">

                  {clusters.map((cluster) => (

                    <div
                      className="cluster-card"
                      key={cluster.cluster_id}
                      onClick={() =>
                        investigateCluster(cluster.cluster_id)
                      }
                    >

                      <div className="cluster-header">
                        <div>
                          <small>CLUSTER</small>
                          <h3>{cluster.cluster_id}</h3>
                        </div>

                        <span
                          className={`badge ${routingClass(
                            cluster.routing
                          )}`}
                        >
                          {formatRouting(cluster.routing)}
                        </span>
                      </div>

                      <div className="risk">
                        <span>Risk Score</span>
                        <strong>
                          {Number(cluster.risk_score).toFixed(1)}
                        </strong>
                      </div>

                      <div className="details">

                        <div>
                          <span>Classification</span>
                          <b>{cluster.classification}</b>
                        </div>

                        <div>
                          <span>Customers</span>
                          <b>{cluster.member_customer_count}</b>
                        </div>

                        <div>
                          <span>Transactions</span>
                          <b>{cluster.transaction_count}</b>
                        </div>

                        <div>
                          <span>Shared IDs</span>
                          <b>{cluster.shared_identifier_types}</b>
                        </div>

                        <div>
                          <span>Short Refunds</span>
                          <b>{cluster.short_refund_count}</b>
                        </div>

                        <div>
                          <span>Merchants</span>
                          <b>{cluster.merchant_fanout_count}</b>
                        </div>

                      </div>

                      <div className="view">
                        View investigation →
                      </div>

                    </div>

                  ))}

                </div>

              )}

            </section>

            {investigating && (
              <section className="investigation loading-investigation">
                <div className="spinner"></div>
                <h2>Investigating cluster...</h2>
              </section>
            )}

            {investigation && !investigating && (

              <section className="investigation">

                <div className="section-title">
                  <div>
                    <div className="eyebrow">
                      INVESTIGATION
                    </div>

                    <h2>{investigation.case_id}</h2>
                  </div>

                  <span className="badge investigate">
                    {formatRouting(
                      investigation.recommendation
                    )}
                  </span>
                </div>

                <div className="summary-box">
                  <div className="eyebrow">INVESTIGATOR SUMMARY</div>
                  <p>{investigation.summary}</p>
                </div>

                <div className="evidence">

                  <h3>Observed Evidence</h3>

                  {investigation.observed_evidence?.map(
                    (item, index) => (
                      <div
                        className="evidence-item"
                        key={index}
                      >
                        <span>EV-{index + 1}</span>
                        <p>{item}</p>
                      </div>
                    )
                  )}

                </div>

                <div className="two-column">

                  <div>
                    <h3>Benign Alternatives</h3>

                    {investigation.benign_alternatives?.map(
                      (item, index) => (
                        <p key={index}>• {item}</p>
                      )
                    )}
                  </div>

                  <div>
                    <h3>Uncertainty</h3>

                    {investigation.uncertainty?.map(
                      (item, index) => (
                        <p key={index}>• {item}</p>
                      )
                    )}
                  </div>

                </div>

                <div className="review">

                  <h3>Human Review Questions</h3>

                  <ol>
                    {investigation.review_questions?.map(
                      (question, index) => (
                        <li key={index}>{question}</li>
                      )
                    )}
                  </ol>

                </div>

                <div className="citations">
                  <span>CITED EVIDENCE</span>

                  {investigation.cited_evidence_ids?.map(
                    (id) => (
                      <b key={id}>{id}</b>
                    )
                  )}
                </div>

              </section>

            )}

          </>
        )}

      </main>
    </div>
  );
}

export default App;

