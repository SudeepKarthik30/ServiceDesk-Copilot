import json

from django.conf import settings
from django.core.management.base import BaseCommand
from qdrant_client import models

from ai.embeddings import get_dense_model, get_sparse_model
from ai.qdrant_client import ensure_collection, get_client

INDEXED_PATH = settings.BASE_DIR.parent / "data" / "processed" / "tickets.jsonl"
BATCH_SIZE = 128


class Command(BaseCommand):
    help = "Embed data/processed/tickets.jsonl (dense + BM25 sparse) and upsert into Qdrant."

    def handle(self, *args, **options):
        if not INDEXED_PATH.exists():
            self.stderr.write(f"{INDEXED_PATH} not found - run `manage.py clean_dataset` first.")
            return

        with open(INDEXED_PATH, encoding="utf-8") as f:
            rows = [json.loads(line) for line in f]
        self.stdout.write(f"Loaded {len(rows)} rows to index.")

        client = get_client()
        ensure_collection(client, settings.QDRANT_COLLECTION)

        dense_model = get_dense_model()
        sparse_model = get_sparse_model()

        indexed = 0
        for start in range(0, len(rows), BATCH_SIZE):
            batch = rows[start : start + BATCH_SIZE]
            texts = [f"{r['subject']}\n{r['body']}" for r in batch]

            dense_vecs = list(dense_model.embed(texts))
            sparse_vecs = list(sparse_model.embed(texts))

            points = [
                models.PointStruct(
                    id=row["id"],
                    vector={
                        "dense": dense.tolist(),
                        "sparse": models.SparseVector(
                            indices=sparse.indices.tolist(), values=sparse.values.tolist()
                        ),
                    },
                    payload={
                        "subject": row["subject"],
                        "body": row["body"],
                        "resolution": row["resolution"],
                        "category": row["category"],
                        "queue": row["queue"],
                        "priority": row["priority"],
                        "language": "en",
                        "resolved": True,
                        "restricted": False,
                        "source": "dataset",
                    },
                )
                for row, dense, sparse in zip(batch, dense_vecs, sparse_vecs)
            ]
            client.upsert(collection_name=settings.QDRANT_COLLECTION, points=points)
            indexed += len(points)
            self.stdout.write(f"Indexed {indexed}/{len(rows)}")

        self.stdout.write(self.style.SUCCESS(f"Done. {indexed} points in '{settings.QDRANT_COLLECTION}'."))
