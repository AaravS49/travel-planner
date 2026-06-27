import json
import re


EXTRACT_PROMPT = """You are a data extraction assistant. Read this travel itinerary and extract the estimated costs for each day, broken into these four categories:

- food: all meals, drinks, coffee, snacks
- activities: admissions, tours, experiences, tickets
- transport: taxis, trains, buses, metro, transfers
- other: accommodation, shopping, tips, miscellaneous

Return ONLY a valid JSON array with no explanation. Use this exact format:
[
  {{"day": 1, "label": "Day 1 — Mon, Jul 10", "food": 45, "activities": 60, "transport": 15, "other": 10}},
  ...
]

If a cost is not mentioned for a category on a given day, estimate 0.
All values must be numbers in {currency}, no symbols.

ITINERARY:
{itinerary}"""


def extract_budget(client, model: str, itinerary: str, currency: str) -> list[dict] | None:
    prompt = EXTRACT_PROMPT.format(currency=currency, itinerary=itinerary)
    try:
        response = client.models.generate_content(model=model, contents=prompt)
        text = response.text.strip()
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception:
        pass
    return None
