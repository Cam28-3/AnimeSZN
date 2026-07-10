import httpx

BASE_URL = "https://api.jikan.moe/v4"

_client = httpx.Client(base_url=BASE_URL, timeout=30.0)


def fetch_streaming(anime_id: int) -> list[dict]:
    """Live, on-demand lookup -- not part of the offline ingestion pipeline, so no
    artificial rate-limit pacing here (that's only needed for the bulk crawler)."""
    try:
        response = _client.get(f"/anime/{anime_id}/streaming")
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return []
        raise
    return [{"name": entry["name"], "url": entry["url"]} for entry in response.json().get("data", [])]
