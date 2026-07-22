import { useState } from "react";
import { apiFetch, setStoredKey } from "./api";

// Password-style key entry shown when no valid access key is stored. Probes /discover (a
// cheap, real endpoint) rather than trusting the key blindly, so a wrong key is caught here
// instead of surfacing as a confusing failure on the first real query.
export default function AccessGate({ onUnlocked }) {
  const [key, setKey] = useState("");
  const [error, setError] = useState(null);
  const [checking, setChecking] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!key.trim() || checking) return;
    setChecking(true);
    setError(null);
    setStoredKey(key.trim());
    try {
      const res = await apiFetch("/discover");
      if (!res.ok) throw new Error();
      onUnlocked();
    } catch {
      setError("That key didn't work. Check it and try again.");
    } finally {
      setChecking(false);
    }
  }

  return (
    <div className="app">
      <h1 className="wordmark">
        ANIME<span className="wordmark-accent">SZN</span>
      </h1>
      <p className="tagline">This is a limited preview. Enter your access key to continue.</p>
      <form onSubmit={handleSubmit} className="query-form">
        <input
          type="password"
          value={key}
          onChange={(e) => setKey(e.target.value)}
          placeholder="Access key"
          disabled={checking}
          autoFocus
        />
        <button type="submit" disabled={checking || !key.trim()}>
          {checking ? "Checking..." : "Enter"}
        </button>
      </form>
      {error && <p className="error">{error}</p>}
    </div>
  );
}
