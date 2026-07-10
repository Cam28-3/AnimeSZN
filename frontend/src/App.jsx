import { useState } from "react";
import "./App.css";

const API_BASE = "http://localhost:8000";

function WhereToWatch({ animeId }) {
  const [state, setState] = useState("idle"); // idle | loading | loaded | error
  const [platforms, setPlatforms] = useState([]);

  async function handleClick() {
    if (state === "loading") return;
    setState("loading");
    try {
      const res = await fetch(`${API_BASE}/anime/${animeId}`);
      if (!res.ok) throw new Error();
      const data = await res.json();
      setPlatforms(data.streaming);
      setState("loaded");
    } catch {
      setState("error");
    }
  }

  if (state === "idle") {
    return (
      <button type="button" className="watch-link" onClick={handleClick}>
        Where to watch →
      </button>
    );
  }

  if (state === "loading") {
    return <p className="watch-status">Looking that up...</p>;
  }

  if (state === "error") {
    return <p className="watch-status">Couldn't fetch streaming info.</p>;
  }

  if (platforms.length === 0) {
    return <p className="watch-status">No streaming platforms listed.</p>;
  }

  return (
    <div className="watch-links">
      {platforms.map((p) => (
        <a key={p.name} href={p.url} target="_blank" rel="noopener noreferrer" className="watch-pill">
          {p.name}
        </a>
      ))}
    </div>
  );
}

function RecommendationCard({ rec }) {
  return (
    <div className="card">
      {rec.image_url && (
        <div className="card-image">
          <img src={rec.image_url} alt="" loading="lazy" />
        </div>
      )}
      <div className="card-body">
        <div className="card-header">
          <h3>{rec.title}</h3>
          {rec.score != null && <span className="score">{rec.score.toFixed(2)}</span>}
        </div>
        <p className="rationale">{rec.rationale}</p>
        {rec.caveat && <p className="caveat">⚠ {rec.caveat}</p>}
        <WhereToWatch animeId={rec.anime_id} />
      </div>
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
      <h1 className="wordmark">
        ANIME<span className="wordmark-accent">SZN</span>
      </h1>
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
