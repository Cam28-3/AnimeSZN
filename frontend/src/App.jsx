import { useEffect, useRef, useState } from "react";
import "./App.css";
import myLogo from "./animeszn_logo_white_text.png";

const API_BASE = "http://localhost:8000";

const PLACEHOLDER_EXAMPLES = [
  "Something like Attack on Titan...",
  "A wholesome slice-of-life show...",
  "A psychological thriller with a twist...",
  "More like Death Note...",
  "A short series I can binge in a weekend...",
  "I'm new to anime, what should I watch first?",
];
const PLACEHOLDER_INTERVAL_MS = 3000;

// Fallback link to a title's AniList page, shown alongside (or instead of) streaming platform
// links -- always available since every ingested title has an AniList id.
function AniListPill({ url }) {
  return (
    <a href={url} target="_blank" rel="noopener noreferrer" className="watch-pill watch-pill-anilist">
      AniList ↗
    </a>
  );
}

// Lazy "Where to watch" expander shown on every card -- only hits GET /anime/{id} (the live
// AniList streaming-links lookup) once the user actually clicks, not on initial render.
function WhereToWatch({ animeId }) {
  const [state, setState] = useState("idle"); // idle | loading | loaded | error | unavailable
  const [platforms, setPlatforms] = useState([]);
  const [anilistUrl, setAnilistUrl] = useState(null);

  async function handleClick() {
    if (state === "loading") return;
    setState("loading");
    try {
      const res = await fetch(`${API_BASE}/anime/${animeId}`);
      if (!res.ok) throw new Error();
      const data = await res.json();
      setAnilistUrl(data.anilist_url);
      if (data.streaming_unavailable) {
        setState("unavailable");
        return;
      }
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

  if (state === "unavailable") {
    return (
      <div>
        <p className="watch-status">
          Streaming source is temporarily down —{" "}
          <button type="button" className="watch-link" onClick={handleClick}>
            try again
          </button>
        </p>
        {anilistUrl && (
          <div className="watch-links">
            <AniListPill url={anilistUrl} />
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="watch-links">
      {platforms.map((p) => (
        <a key={p.name} href={p.url} target="_blank" rel="noopener noreferrer" className="watch-pill">
          {p.name}
        </a>
      ))}
      {anilistUrl && <AniListPill url={anilistUrl} />}
    </div>
  );
}

// Standard grid card for a recommendation (used when a turn has multiple recommendations).
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

// Wide single-title layout used when a turn has exactly one recommendation, instead of
// cramming it into the multi-item grid.
function SpotlightCard({ rec }) {
  return (
    <div className="card spotlight-card">
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

// Homepage discovery-grid card (currently-airing titles) -- clicking it prefills the query
// box via onPick rather than issuing its own recommend request.
function DiscoverCard({ item, onPick }) {
  return (
    <div className="card discover-card">
      {item.image_url && (
        <div className="card-image" onClick={() => onPick(item.title)}>
          <img src={item.image_url} alt="" loading="lazy" />
        </div>
      )}
      <div className="card-body">
        <div className="card-header" onClick={() => onPick(item.title)}>
          <h3>{item.title}</h3>
          {item.score != null && <span className="score">{item.score.toFixed(2)}</span>}
        </div>
        {item.genres.length > 0 && <p className="genre-tags">{item.genres.join(" · ")}</p>}
        <WhereToWatch animeId={item.anime_id} />
      </div>
    </div>
  );
}

// Root component: query box, spoiler toggle, homepage discovery grid, and the growing list of
// conversation turns. All state is client-side only -- no backend session storage.
function App() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [turns, setTurns] = useState([]);
  const [expandedTurns, setExpandedTurns] = useState(new Set());
  const [discoverItems, setDiscoverItems] = useState([]);
  const [spoilerFree, setSpoilerFree] = useState(true);
  const [placeholderIndex, setPlaceholderIndex] = useState(0);
  const inputRef = useRef(null);

  useEffect(() => {
    fetch(`${API_BASE}/discover`)
      .then((res) => (res.ok ? res.json() : []))
      .then(setDiscoverItems)
      .catch(() => setDiscoverItems([]));
  }, []);

  // Cycles the search box's placeholder through a few example queries -- paused while the
  // user has actually typed something, since the placeholder is hidden then anyway.
  useEffect(() => {
    if (query) return;
    const id = setInterval(() => {
      setPlaceholderIndex((i) => (i + 1) % PLACEHOLDER_EXAMPLES.length);
    }, PLACEHOLDER_INTERVAL_MS);
    return () => clearInterval(id);
  }, [query]);

  // Expands/collapses a past conversation turn's recommendations (the latest turn is always
  // shown expanded regardless of this state -- see isExpanded below).
  function toggleTurn(index) {
    setExpandedTurns((prev) => {
      const next = new Set(prev);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  }

  // Clicking a discovery-grid card prefills a "something like X" query rather than
  // recommending it directly, so the agent still reasons about it (tool calls, reception check).
  function pickDiscoverItem(title) {
    setQuery(`something like ${title}`);
    inputRef.current?.focus();
  }

  // Submits the query to POST /recommend, sending prior turns as history (id + title only, not
  // full recommendation objects) so the agent has multi-turn context, then appends the new turn.
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
        body: JSON.stringify({ query, history, spoiler_free: spoilerFree }),
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
        <h1 className="logo">
          <img src={myLogo} alt="Anime SZN" className="logo-image" />
        </h1>
        {turns.length > 0 && (
          <button type="button" className="reset-button" onClick={() => setTurns([])}>
            New conversation
          </button>
        )}
      </div>
      <p className="tagline">Find something to watch, where to watch it, and what the world thinks.</p>

      <form onSubmit={handleSubmit} className="query-form">
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={PLACEHOLDER_EXAMPLES[placeholderIndex]}
          disabled={loading}
        />
        <button type="submit" disabled={loading || !query.trim()}>
          {loading ? "Thinking..." : "Ask"}
        </button>
      </form>

      <label className="spoiler-toggle">
        <input
          type="checkbox"
          checked={spoilerFree}
          onChange={(e) => setSpoilerFree(e.target.checked)}
        />
        <span className="spoiler-toggle-track">
          <span className="spoiler-toggle-thumb" />
        </span>
        <span>Spoiler-free mode</span>
      </label>

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
                  {t.recommendations.length === 1 ? (
                    <SpotlightCard rec={t.recommendations[0]} />
                  ) : (
                    <div className="card-grid">
                      {t.recommendations.map((rec) => (
                        <RecommendationCard key={rec.anime_id} rec={rec} />
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
          );
        })}
    </div>
  );
}

export default App;
