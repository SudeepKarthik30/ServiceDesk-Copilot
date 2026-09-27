"""Manual, human-curated add/remove-from-KB actions (see CLAUDE.md "Add to KB"). Separate from the
bulk dataset/manual-article seed commands - this indexes one resolved ticket at a time, id-namespaced
well above both the dataset's ids (0..~23641) and the seed_kb.py articles (900001+) so they never collide.
"""

from django.conf import settings
from qdrant_client import models as qm

from ai.embeddings import get_dense_model, get_sparse_model
from ai.pii import mask_pii
from ai.qdrant_client import ensure_collection, get_client

TICKET_KB_ID_OFFSET = 1_000_000


def _point_id(ticket):
    return TICKET_KB_ID_OFFSET + ticket.id


def upsert_ticket_kb_entry(ticket, subject, body, resolution):
    subject = mask_pii(subject)
    body = mask_pii(body)
    resolution = mask_pii(resolution)

    client = get_client()
    ensure_collection(client, settings.QDRANT_COLLECTION)
    dense_model = get_dense_model()
    sparse_model = get_sparse_model()

    text = f"{subject}\n{body}"
    dense_vec = next(dense_model.embed([text]))
    sparse_vec = next(sparse_model.embed([text]))

    client.upsert(
        collection_name=settings.QDRANT_COLLECTION,
        points=[
            qm.PointStruct(
                id=_point_id(ticket),
                vector={
                    "dense": dense_vec.tolist(),
                    "sparse": qm.SparseVector(
                        indices=sparse_vec.indices.tolist(), values=sparse_vec.values.tolist()
                    ),
                },
                payload={
                    "subject": subject,
                    "body": body,
                    "resolution": resolution,
                    "category": ticket.category.name if ticket.category else None,
                    "queue": "IT Support",
                    "priority": ticket.urgency,
                    "language": "en",
                    "resolved": True,
                    "restricted": False,
                    "source": "ticket_kb",
                    "ticket_id": ticket.id,
                },
            )
        ],
    )


def remove_ticket_kb_entry(ticket):
    get_client().delete(
        collection_name=settings.QDRANT_COLLECTION,
        points_selector=qm.PointIdsList(points=[_point_id(ticket)]),
    )
