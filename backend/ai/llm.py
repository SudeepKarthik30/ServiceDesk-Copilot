import json
from functools import lru_cache

from django.conf import settings
from openai import OpenAI


@lru_cache
def get_client():
    return OpenAI(base_url=settings.LLM_BASE_URL, api_key=settings.LLM_API_KEY)


def chat_json(model, system, user, temperature=0.0):
    """Call the chat endpoint and parse the reply as JSON. Raises on any transport/parse error -
    callers (pipeline.py) treat that as an AI error and escalate."""
    response = get_client().chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)
