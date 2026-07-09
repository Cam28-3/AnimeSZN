import { useState } from "react";
import "./App.css";

const API_BASE = "http://localhost:8000";

function RecommendationCard({ rec }) {
  return (
    <div className="card">
      <div className="card-header">
        <h3>{rec.title}</h3>
        {rec.score != null && <span className="score">{rec.score.toFixed(2)}</span>}
      </div>
      <p className="rationale">{rec.rationale}</p>
      {rec.caveat && <p className="caveat">⚠ {rec.caveat}</p>}
    </div>
  );
}

function App() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!query.trim() || loading) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await fetch(`${API_BASE}/recommend`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      });
      if (!res.ok) throw new Error(`Request failed (${res.status})`);
      const data = await res.json();
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app">
      <h1>AnimeSZN</h1>
      <p className="tagline">Find or discover anime — the agent checks community reception before recommending.</p>

      <form onSubmit={handleSubmit} className="query-form">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="e.g. something like Death Note, or a wholesome slice-of-life show"
          disabled={loading}
        />
        <button type="submit" disabled={loading || !query.trim()}>
          {loading ? "Thinking..." : "Ask"}
        </button>
      </form>

      {error && <p className="error">{error}</p>}

      {result && (
        <div className="results">
          <p className="agent-message">{result.message}</p>
          <div className="card-grid">
            {result.recommendations.map((rec) => (
              <RecommendationCard key={rec.anime_id} rec={rec} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
