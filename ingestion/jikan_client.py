import time

import httpx

BASE_URL = "https://api.jikan.moe/v4"
REQUEST_INTERVAL_SECONDS = 1.0  # Jikan asks for ~3/sec; we stay well under that

_client = httpx.Client(base_url=BASE_URL, timeout=30.0)


def _get(path: str, params: dict | None = None) -> dict:
    response = _client.get(path, params=params)
    response.raise_for_status()
    time.sleep(REQUEST_INTERVAL_SECONDS)
    return response.json()


def fetch_anime_page(page: int) -> tuple[list[dict], bool]:
    """Returns (entries, has_next_page)."""
    data = _get("/anime", params={"page": page, "order_by": "popularity", "sort": "asc"})
    entries = data["data"]
    has_next_page = data["pagination"]["has_next_page"]
    return entries, has_next_page


def iter_anime(max_pages: int | None = None):
    page = 1
    while True:
        entries, has_next_page = fetch_anime_page(page)
        yield from entries
        if not has_next_page:
            break
        if max_pages is not None and page >= max_pages:
            break
        page += 1
