import { useEffect, useRef, useState } from "react";
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

function DiscoverCard({ item, onPick }) {
  return (
    <button type="button" className="card discover-card" onClick={() => onPick(item.title)}>
      {item.image_url && (
        <div className="card-image">
          <img src={item.image_url} alt="" loading="lazy" />
        </div>
      )}
      <div className="card-body">
        <div className="card-header">
          <h3>{item.title}</h3>
          {item.score != null && <span className="score">{item.score.toFixed(2)}</span>}
        </div>
        {item.genres.length > 0 && <p className="genre-tags">{item.genres.join(" · ")}</p>}
      </div>
    </button>
  );
}

function App() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [turns, setTurns] = useState([]);
  const [expandedTurns, setExpandedTurns] = useState(new Set());
  const [discoverItems, setDiscoverItems] = useState([]);
  const inputRef = useRef(null);

  useEffect(() => {
    fetch(`${API_BASE}/discover`)
      .then((res) => (res.ok ? res.json() : []))
      .then(setDiscoverItems)
      .catch(() => setDiscoverItems([]));
  }, []);

  function toggleTurn(index) {
    setExpandedTurns((prev) => {
      const next = new Set(prev);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  }

  function pickDiscoverItem(title) {
    setQuery(`something like ${title}`);
    inputRef.current?.focus();
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!query.trim() || loading) return;

    setLoading(true);
    setError(null);

    const history = turns.map((t) => ({
      query: t.query,
      message: t.message,
      recommendations: t.recommendations.map((r) => ({ anime_id: r.anime_id, title: r.title })),
    }));

    try {
      const res = await fetch(`${API_BASE}/recommend`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, history }),
      });
      if (!res.ok) throw new Error(`Request failed (${res.status})`);
      const data = await res.json();
      setTurns((prev) => [...prev, { query, message: data.message, recommendations: data.recommendations }]);
      setQuery("");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app">
      <div className="header-row">
        <h1 className="wordmark">
          ANIME<span className="wordmark-accent">SZN</span>
        </h1>
        {turns.length > 0 && (
          <button type="button" className="reset-button" onClick={() => setTurns([])}>
            New conversation
          </button>
        )}
      </div>
      <p className="tagline">Find or discover anime — the agent checks community reception before recommending.</p>

      <form onSubmit={handleSubmit} className="query-form">
        <input
          ref={inputRef}
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

      {turns.length === 0 && discoverItems.length > 0 && (
        <div className="discover-section">
          <h2 className="discover-heading">Airing now</h2>
          <div className="card-grid">
            {discoverItems.map((item) => (
              <DiscoverCard key={item.anime_id} item={item} onPick={pickDiscoverItem} />
            ))}
          </div>
        </div>
      )}

      {turns
        .map((t, i) => ({ t, i }))
        .reverse()
        .map(({ t, i }) => {
          const isLatest = i === turns.length - 1;
          const isExpanded = isLatest || expandedTurns.has(i);
          return (
            <div className={`turn ${isExpanded ? "expanded" : "collapsed"}`} key={i}>
              <button type="button" className="turn-header" onClick={() => toggleTurn(i)}>
                <span className="user-query">You asked: {t.query}</span>
                <span className="turn-toggle">{isExpanded ? "▲" : "▼"}</span>
              </button>
              {isExpanded && (
                <>
                  <p className="agent-message">{t.message}</p>
                  <div className="card-grid">
                    {t.recommendations.map((rec) => (
                      <RecommendationCard key={rec.anime_id} rec={rec} />
                    ))}
                  </div>
                </>
              )}
            </div>
          );
        })}
    </div>
  );
}

export default App;
