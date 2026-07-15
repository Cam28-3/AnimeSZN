import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

BASE_URL = "https://api.jikan.moe/v4"

_client = httpx.Client(base_url=BASE_URL, timeout=30.0)


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in (429, 502, 503, 504)


@retry(
    retry=retry_if_exception(_is_retryable),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    stop=stop_after_attempt(3),
    reraise=True,
)
def _get_streaming(anime_id: int) -> httpx.Response:
    response = _client.get(f"/anime/{anime_id}/streaming")
    response.raise_for_status()
    return response


def fetch_streaming(anime_id: int) -> list[dict]:
    """Live, on-demand lookup -- not part of the offline ingestion pipeline, so no
    artificial rate-limit pacing here (that's only needed for the bulk crawler). Retries a
    couple of times on transient errors/5xx/429, but fails fast rather than making the user
    wait through a long backoff if Jikan is having a sustained outage."""
    try:
        response = _get_streaming(anime_id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return []
        raise
    return [{"name": entry["name"], "url": entry["url"]} for entry in response.json().get("data", [])]
