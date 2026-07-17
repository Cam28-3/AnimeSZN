import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

BASE_URL = "https://graphql.anilist.co"

_client = httpx.Client(base_url=BASE_URL, timeout=10.0)

STREAMING_QUERY = """
query ($id: Int) {
  Media(id: $id, type: ANIME) {
    externalLinks { site url type }
  }
}
"""


# Transient-failure classifier shared by the retry decorator below: network errors and
# rate-limit/server-error status codes are worth retrying, everything else isn't.
def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in (429, 500, 502, 503, 504)


@retry(
    retry=retry_if_exception(_is_retryable),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    stop=stop_after_attempt(3),
    reraise=True,
)
# Fires the streaming-links GraphQL query for one anime id, with a short retry/backoff for
# transient failures.
def _post(anime_id: int) -> httpx.Response:
    response = _client.post("", json={"query": STREAMING_QUERY, "variables": {"id": anime_id}})
    response.raise_for_status()
    return response


def fetch_streaming(anime_id: int) -> list[dict]:
    """Live, on-demand lookup -- not part of the offline ingestion pipeline, so no artificial
    rate-limit pacing here (that's only needed for the bulk crawler). Retries a couple of times
    on transient errors/5xx/429, but fails fast rather than making the user wait through a long
    backoff if AniList is having a sustained outage."""
    try:
        response = _post(anime_id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return []
        raise
    media = response.json().get("data", {}).get("Media")
    if not media:
        return []
    links = media.get("externalLinks") or []
    return [{"name": link["site"], "url": link["url"]} for link in links if link.get("type") == "STREAMING"]
