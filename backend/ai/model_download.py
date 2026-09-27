"""Fetches fastembed's ONNX model files ourselves via huggingface_hub.hf_hub_download().

Why: fastembed's own downloader calls huggingface_hub's `model_info()` / `list_repo_tree()`,
which hit `huggingface.co/api/models/...`. On this network that endpoint's TLS handshake is
reset every time, while `huggingface.co/<repo>/resolve/main/<file>` (what hf_hub_download uses)
works fine. hf_hub_download also has its own retry/backoff for transient resets, so we use it
directly to populate the cache, then hand fastembed the resulting directory via
`specific_model_path` - which skips fastembed's own (broken) download path entirely.
"""

import os

from huggingface_hub import hf_hub_download
from huggingface_hub.errors import EntryNotFoundError

STANDARD_FILES = [
    "config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "preprocessor_config.json",
]


def fetch_model_dir(hf_source_repo, required_files):
    """Download `required_files` (best-effort) plus the standard config files for a repo.

    Returns the local snapshot root directory all of them were downloaded into - NOT the parent of
    the last file. Some models' `model_file` lives in a subfolder (e.g. cross-encoders ship
    "onnx/model.onnx"), and fastembed re-joins `specific_model_path / model_file` itself, so the
    root must be stripped of the whole relative filename, not just its last path segment.
    """
    local_dir = None
    for filename in STANDARD_FILES + list(required_files):
        try:
            path = hf_hub_download(repo_id=hf_source_repo, filename=filename, revision="main")
        except EntryNotFoundError:
            continue
        suffix = filename.replace("/", os.sep)
        local_dir = path[: -len(suffix)].rstrip(os.sep)
    if local_dir is None:
        raise RuntimeError(f"Could not download any files for {hf_source_repo}")
    return local_dir


def get_model_kwargs(model_description):
    """Build the {specific_model_path: ...} kwarg for a fastembed model description."""
    required = [model_description.model_file, *model_description.additional_files]
    model_dir = fetch_model_dir(model_description.sources.hf, required)
    return {"specific_model_path": model_dir}
