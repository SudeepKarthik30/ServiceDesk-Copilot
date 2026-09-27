from functools import lru_cache

from django.conf import settings
from fastembed.rerank.cross_encoder import TextCrossEncoder

from ai.model_download import get_model_kwargs


@lru_cache
def get_reranker():
    desc = next(m for m in TextCrossEncoder._list_supported_models() if m.model == settings.RERANK_MODEL)
    return TextCrossEncoder(model_name=settings.RERANK_MODEL, **get_model_kwargs(desc))
