"""Maps the HF dataset's `queue` field to one of our seeded Category names (see tickets/management/commands/seed.py).

The source dataset is generic multi-industry customer support, not IT-helpdesk-specific, so this
mapping is a best-effort approximation rather than a precise match. That's acceptable because the
triage pipeline's retrieval step doesn't hard-filter by category (see CLAUDE.md) - category here is
descriptive metadata on KB entries, not a search gate.
"""

QUEUE_TO_CATEGORY = {
    "Service Outages and Maintenance": "Network Outage",
    "Technical Support": "Software Installation",
    "IT Support": "Account Access",
    "Product Support": "Laptop Issue",
    "Returns and Exchanges": "Peripheral Request",
    "Customer Service": "Password Reset",
    "Billing and Payments": "Account Access",
    "Sales and Pre-Sales": "Software Installation",
    "Human Resources": "Account Access",
    "General Inquiry": "Password Reset",
}


def map_queue_to_category(queue):
    return QUEUE_TO_CATEGORY.get(queue)
