import hashlib
import json
import random
import re

from django.conf import settings
from django.core.management.base import BaseCommand

from ai.category_map import map_queue_to_category
from ai.pii import mask_pii

RAW_PATH = settings.BASE_DIR.parent / "data" / "raw" / "customer_support_tickets.jsonl"
PROCESSED_DIR = settings.BASE_DIR.parent / "data" / "processed"
INDEXED_PATH = PROCESSED_DIR / "tickets.jsonl"
HOLDOUT_PATH = PROCESSED_DIR / "eval_holdout.jsonl"

HOLDOUT_SIZE = 100
HOLDOUT_SEED = 42

_WHITESPACE_RE = re.compile(r"\s+")


def _normalize(text):
    return _WHITESPACE_RE.sub(" ", (text or "").strip().lower())


def _unescape_newlines(text):
    """The source dataset stores newlines as a literal backslash-n, not an actual newline char."""
    return (text or "").replace("\\n", "\n")


def _dedupe_key(row):
    return hashlib.sha256((_normalize(row["subject"]) + "|" + _normalize(row["body"])).encode("utf-8")).hexdigest()


class Command(BaseCommand):
    help = (
        "Clean the raw dataset: keep English tickets with a real answer, dedupe, mask PII, "
        "map queue -> category, and hold out a random sample for later evaluation (not indexed)."
    )

    def handle(self, *args, **options):
        if not RAW_PATH.exists():
            self.stderr.write(f"{RAW_PATH} not found - run `manage.py download_dataset` first.")
            return

        seen = set()
        kept = []
        total = 0
        dropped_language = 0
        dropped_no_answer = 0
        dropped_duplicate = 0
        dropped_no_category = 0

        with open(RAW_PATH, encoding="utf-8") as f:
            for line in f:
                total += 1
                row = json.loads(line)

                if row.get("language") != "en":
                    dropped_language += 1
                    continue
                if not (row.get("answer") or "").strip():
                    dropped_no_answer += 1
                    continue

                key = _dedupe_key(row)
                if key in seen:
                    dropped_duplicate += 1
                    continue
                seen.add(key)

                category = map_queue_to_category(row.get("queue"))
                if category is None:
                    dropped_no_category += 1
                    continue

                kept.append(
                    {
                        "subject": mask_pii(_unescape_newlines(row.get("subject"))),
                        "body": mask_pii(_unescape_newlines(row.get("body"))),
                        "resolution": mask_pii(_unescape_newlines(row.get("answer"))),
                        "queue": row.get("queue"),
                        "category": category,
                        "priority": row.get("priority"),
                    }
                )

        random.Random(HOLDOUT_SEED).shuffle(kept)
        holdout, indexed = kept[:HOLDOUT_SIZE], kept[HOLDOUT_SIZE:]

        for i, row in enumerate(indexed):
            row["id"] = i
        for i, row in enumerate(holdout):
            row["id"] = i

        PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        with open(INDEXED_PATH, "w", encoding="utf-8") as f:
            for row in indexed:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        with open(HOLDOUT_PATH, "w", encoding="utf-8") as f:
            for row in holdout:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

        self.stdout.write(
            f"Read {total} rows. Dropped: {dropped_language} non-English, {dropped_no_answer} no answer, "
            f"{dropped_duplicate} duplicates, {dropped_no_category} unmapped queue."
        )
        self.stdout.write(self.style.SUCCESS(f"Wrote {len(indexed)} rows to {INDEXED_PATH}"))
        self.stdout.write(self.style.SUCCESS(f"Wrote {len(holdout)} eval holdout rows to {HOLDOUT_PATH}"))
