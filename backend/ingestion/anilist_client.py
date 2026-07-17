"""AniList GraphQL client for the offline ingestion pipeline.

AniList hard-caps offset pagination at 5000 entries per query, regardless of sort order or
filter ("Page depth exceeds maximum allowed for API requests (5000 entries)") -- so a single
popularity-sorted crawl (what Jikan supported) can't reach the full catalog. Instead this
crawls year by year via startDate ranges, comfortably under the cap per year, to cover the
whole catalog. Titles with no startDate at all (unannounced/TBA) fall outside every window and
are not ingested -- an acceptable gap since they also have no synopsis/score/reviews yet.
"""

import time

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

BASE_URL = "https://graphql.anilist.co"
REQUEST_INTERVAL_SECONDS = 2.5  # AniList's public rate limit is 30 req/min; stay well under it
PER_PAGE = 50
EARLIEST_YEAR = 1900
LATEST_YEAR = 2027  # covers announced/upcoming titles

_client = httpx.Client(base_url=BASE_URL, timeout=30.0)

MEDIA_PAGE_QUERY = """
query ($page: Int, $perPage: Int, $from: FuzzyDateInt, $to: FuzzyDateInt) {
  Page(page: $page, perPage: $perPage) {
    pageInfo { hasNextPage }
    media(type: ANIME, startDate_greater: $from, startDate_lesser: $to, sort: START_DATE) {
      id
      idMal
      title { romaji english }
      description
      genres
      tags { name rank isMediaSpoiler isGeneralSpoiler }
      episodes
      status
      startDate { year month day }
      averageScore
      popularity
      coverImage { large }
    }
  }
}
"""

REVIEWS_QUERY = """
query ($id: Int, $perPage: Int) {
  Media(id: $id, type: ANIME) {
    reviews(perPage: $perPage, sort: RATING_DESC) {
      nodes { body(asHtml: false) }
    }
  }
}
"""


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in (429, 500, 502, 503, 504)


@retry(
    retry=retry_if_exception(_is_retryable),
    wait=wait_exponential(multiplier=2, min=5, max=60),
    stop=stop_after_attempt(6),
    reraise=True,
)
def _post(query: str, variables: dict) -> dict:
    response = _client.post("", json={"query": query, "variables": variables})
    response.raise_for_status()
    time.sleep(REQUEST_INTERVAL_SECONDS)
    payload = response.json()
    if "errors" in payload:
        # AniList returns 200 with an "errors" array for some failure modes (e.g. rate limiting
        # under load) -- surface these as HTTPStatusError so the retry logic above catches them.
        raise httpx.HTTPStatusError(str(payload["errors"]), request=response.request, response=response)
    return payload["data"]


def _year_windows(start_year: int):
    for year in range(start_year, LATEST_YEAR + 1):
        # Pad by 1 on both sides: covers fuzzy year-only dates (stored as YYYY0000, which a
        # strict "greater than YYYY0101" would otherwise exclude) and avoids relying on whether
        # AniList's _greater/_lesser filters are inclusive or exclusive at the boundary. Adjacent
        # windows overlapping by a day is harmless -- ingestion upserts are idempotent by id.
        yield year * 10000 - 1, (year + 1) * 10000 + 1


def iter_anime(start_year: int = EARLIEST_YEAR):
    """Yields raw AniList media entries across every year, working around AniList's
    5000-entries-per-query pagination cap by slicing the crawl by startDate year."""
    for from_date, to_date in _year_windows(start_year):
        page = 1
        while True:
            data = _post(MEDIA_PAGE_QUERY, {"page": page, "perPage": PER_PAGE, "from": from_date, "to": to_date})
            entries = data["Page"]["media"]
            yield from entries
            if not data["Page"]["pageInfo"]["hasNextPage"]:
                break
            page += 1


def fetch_reviews(anilist_id: int, max_reviews: int = 6) -> list[str]:
    data = _post(REVIEWS_QUERY, {"id": anilist_id, "perPage": max_reviews})
    media = data.get("Media")
    if not media:
        return []
    nodes = media.get("reviews", {}).get("nodes", [])
    return [n["body"] for n in nodes if n.get("body")]
