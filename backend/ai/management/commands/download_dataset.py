import json

from django.conf import settings
from django.core.management.base import BaseCommand

DATASET_NAME = "Tobi-Bueck/customer-support-tickets"
RAW_PATH = settings.BASE_DIR.parent / "data" / "raw" / "customer_support_tickets.jsonl"

FIELDS = ["subject", "body", "answer", "type", "queue", "priority", "language"]


class Command(BaseCommand):
    help = f"Download the {DATASET_NAME} dataset from Hugging Face into data/raw/ (all rows, all languages)."

    def handle(self, *args, **options):
        from datasets import load_dataset

        self.stdout.write(f"Downloading {DATASET_NAME} ...")
        ds = load_dataset(DATASET_NAME)["train"]

        RAW_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(RAW_PATH, "w", encoding="utf-8") as f:
            for row in ds:
                f.write(json.dumps({k: row.get(k) for k in FIELDS}, ensure_ascii=False) + "\n")

        self.stdout.write(self.style.SUCCESS(f"Wrote {len(ds)} rows to {RAW_PATH}"))
