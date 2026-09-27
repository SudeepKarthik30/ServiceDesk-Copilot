from functools import lru_cache

from django.conf import settings
from qdrant_client import QdrantClient, models


@lru_cache
def get_client():
    return QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)


def ensure_collection(client, collection_name, dense_size=384):
    """Create the collection with named vectors `dense` (cosine) and `sparse` (BM25/IDF) if missing."""
    if client.collection_exists(collection_name):
        return
    client.create_collection(
        collection_name=collection_name,
        vectors_config={
            "dense": models.VectorParams(size=dense_size, distance=models.Distance.COSINE),
        },
        sparse_vectors_config={
            "sparse": models.SparseVectorParams(modifier=models.Modifier.IDF),
        },
    )
