import voyageai

from app.config import settings

EMBEDDING_MODEL = "voyage-3"
EMBEDDING_DIM = 1024
MAX_BATCH_SIZE = 64  # stay well under Voyage's per-request text/token limits

_client = voyageai.Client(api_key=settings.voyage_api_key)


def embed_documents(texts: list[str]) -> list[list[float]]:
    """Embed a batch of anime documents (synopsis + tags/genres text)."""
    embeddings: list[list[float]] = []
    for i in range(0, len(texts), MAX_BATCH_SIZE):
        chunk = texts[i : i + MAX_BATCH_SIZE]
        result = _client.embed(chunk, model=EMBEDDING_MODEL, input_type="document")
        embeddings.extend(result.embeddings)
    return embeddings


def embed_query(text: str) -> list[float]:
    """Embed a single user query for similarity search against stored documents."""
    return embed_queries([text])[0]


def embed_queries(texts: list[str]) -> list[list[float]]:
    """Embed a batch of query texts in one request (e.g. for eval runs)."""
    embeddings: list[list[float]] = []
    for i in range(0, len(texts), MAX_BATCH_SIZE):
        chunk = texts[i : i + MAX_BATCH_SIZE]
        result = _client.embed(chunk, model=EMBEDDING_MODEL, input_type="query")
        embeddings.extend(result.embeddings)
    return embeddings


def build_embedding_text(synopsis: str | None, genres: list[str], tags: list[str]) -> str:
    parts = [synopsis or ""]
    if tags:
        parts.append("Themes: " + ", ".join(tags))
    if genres:
        parts.append("Genres: " + ", ".join(genres))
    return "\n".join(p for p in parts if p)
