from functools import lru_cache

from django.conf import settings
from fastembed import SparseTextEmbedding, TextEmbedding

from ai.model_download import get_model_kwargs


@lru_cache
def get_dense_model():
    desc = next(m for m in TextEmbedding._list_supported_models() if m.model == settings.EMBED_MODEL)
    return TextEmbedding(model_name=settings.EMBED_MODEL, **get_model_kwargs(desc))


@lru_cache
def get_sparse_model():
    desc = next(m for m in SparseTextEmbedding._list_supported_models() if m.model == settings.SPARSE_MODEL)
    return SparseTextEmbedding(model_name=settings.SPARSE_MODEL, **get_model_kwargs(desc))
