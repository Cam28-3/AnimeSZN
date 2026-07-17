import voyageai
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import settings

EMBEDDING_MODEL = "voyage-4"
EMBEDDING_DIM = 1024
MAX_BATCH_SIZE = 64  # stay well under Voyage's per-request text/token limits

_client = voyageai.Client(api_key=settings.voyage_api_key)


@retry(
    retry=retry_if_exception_type(voyageai.error.RateLimitError),
    wait=wait_exponential(multiplier=2, min=10, max=90),
    stop=stop_after_attempt(8),
    reraise=True,
)
# Low-level single-request call to Voyage's embed API for one chunk (<= MAX_BATCH_SIZE texts).
# input_type is "document" for catalog rows or "query" for user/eval queries -- Voyage tunes
# the embedding differently for each.
def _embed(chunk: list[str], input_type: str) -> list[list[float]]:
    result = _client.embed(chunk, model=EMBEDDING_MODEL, input_type=input_type)
    return result.embeddings


def embed_documents(texts: list[str]) -> list[list[float]]:
    """Embed a batch of anime documents (synopsis + tags/genres text)."""
    embeddings: list[list[float]] = []
    for i in range(0, len(texts), MAX_BATCH_SIZE):
        chunk = texts[i : i + MAX_BATCH_SIZE]
        embeddings.extend(_embed(chunk, "document"))
    return embeddings


def embed_query(text: str) -> list[float]:
    """Embed a single user query for similarity search against stored documents."""
    return embed_queries([text])[0]


def embed_queries(texts: list[str]) -> list[list[float]]:
    """Embed a batch of query texts in one request (e.g. for eval runs)."""
    embeddings: list[list[float]] = []
    for i in range(0, len(texts), MAX_BATCH_SIZE):
        chunk = texts[i : i + MAX_BATCH_SIZE]
        embeddings.extend(_embed(chunk, "query"))
    return embeddings


# Assembles the text that actually gets embedded for an anime row -- synopsis plus
# labeled tag/genre lists, falling back to just the title if everything else is empty.
def build_embedding_text(title: str, synopsis: str | None, genres: list[str], tags: list[str]) -> str:
    parts = [synopsis or ""]
    if tags:
        parts.append("Themes: " + ", ".join(tags))
    if genres:
        parts.append("Genres: " + ", ".join(genres))
    text = "\n".join(p for p in parts if p)
    # Voyage rejects empty strings; a handful of catalog entries have no synopsis/genres/tags at all.
    return text or title
