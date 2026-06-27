def build_trip_context(
    destinations: list[str],
    start_date,
    end_date,
    adults: int,
    children: int,
    children_ages: str,
    elderly: int,
    currency: str,
    budget_min: int,
    budget_max: int,
    dietary: list[str],
    mobility: list[str],
    fitness: str,
    other_restrictions: str,
    must_dos: str,
    general_interests: str,
) -> str:
    num_days = (end_date - start_date).days

    group_parts = [f"{adults} adult{'s' if adults != 1 else ''}"]
    if children > 0:
        ages_note = f" (ages {children_ages})" if children_ages else ""
        group_parts.append(f"{children} child{'ren' if children != 1 else ''}{ages_note}")
    if elderly > 0:
        group_parts.append(f"{elderly} elderly traveler{'s' if elderly != 1 else ''}")
    group_str = ", ".join(group_parts)

    restrictions_parts = []
    if dietary:
        restrictions_parts.append(f"<dietary>{', '.join(dietary)}</dietary>")
    if mobility:
        restrictions_parts.append(f"<accessibility>{', '.join(mobility)}</accessibility>")
    if other_restrictions:
        restrictions_parts.append(f"<other>{other_restrictions}</other>")
    restrictions_xml = "\n    ".join(restrictions_parts) if restrictions_parts else "<none/>"

    daily_avg = (budget_min + budget_max) // 2 // max(num_days, 1)

    return f"""<trip>
  <route>{" → ".join(destinations)}</route>
  <dates>
    <start>{start_date.strftime("%B %d, %Y")}</start>
    <end>{end_date.strftime("%B %d, %Y")}</end>
    <duration>{num_days} day{"s" if num_days != 1 else ""}</duration>
  </dates>
  <group>{group_str}</group>
  <fitness>{fitness}</fitness>
  <budget>
    <range>{budget_min:,}–{budget_max:,} {currency} total</range>
    <daily_average>~{daily_avg:,} {currency}/day</daily_average>
    <currency>{currency}</currency>
  </budget>
  <restrictions>
    {restrictions_xml}
  </restrictions>
  <interests>
    <must_do>{must_dos.strip() if must_dos.strip() else "None specified"}</must_do>
    <general>{general_interests.strip() if general_interests.strip() else "General sightseeing"}</general>
  </interests>
</trip>"""


def build_itinerary_prompt(trip_context: str, currency: str, fitness: str) -> str:
    return f"""You are an expert travel planner with deep local knowledge. Your task is to produce a practical, enjoyable, and realistic day-by-day itinerary.

<instructions>
  <pacing>Pace activities realistically for a {fitness.lower()} fitness group — do not overload days.</pacing>
  <geography>Sequence activities to minimize travel time between locations each day.</geography>
  <budget>Keep all recommendations within the stated budget. Every cost must be shown in {currency}.</budget>
  <restrictions>Respect every dietary and accessibility restriction in every recommendation — meals, activities, and transport.</restrictions>
  <booking>Flag any activity that requires advance booking with "(book ahead)".</booking>
  <authenticity>Prefer local and authentic experiences over tourist traps.</authenticity>
</instructions>

<trip_details>
{trip_context}
</trip_details>

<output_format>
Use this exact structure for every day. Do not deviate from it.

## Day N — [Day of week], [Date]

**Morning**
- [Activity] at [Location] — [why it suits this group] (~[cost] {currency})

**Afternoon**
- [Activity] at [Location] — [why it suits this group] (~[cost] {currency})

**Evening**
- **Dinner:** [Restaurant name] — [cuisine], [price range] {currency}/person, [why it fits dietary needs]
- [Optional evening activity] (~[cost] {currency})

**Daily Budget Estimate:** [X]–[Y] {currency}
**Tips:** [1–2 practical notes on transport, booking, hours, or accessibility]

---
</output_format>

Now write the complete itinerary:"""


def build_refine_prompt(
    current_itinerary: str,
    chat_history: list[dict],
    user_request: str,
) -> str:
    history_lines = []
    for msg in chat_history:
        role = "user" if msg["role"] == "user" else "assistant"
        history_lines.append(f"  <{role}>{msg['content']}</{role}>")
    history_xml = "\n".join(history_lines) if history_lines else "  <none/>"

    return f"""You are an expert travel planner updating an existing itinerary.

<current_itinerary>
{current_itinerary}
</current_itinerary>

<conversation_history>
{history_xml}
</conversation_history>

<user_request>
{user_request}
</user_request>

<instructions>
  <scope>Apply the requested change precisely and only where asked.</scope>
  <preserve>Leave all unaffected days and sections word-for-word unchanged.</preserve>
  <currency>All prices must remain in the same currency as the original itinerary.</currency>
  <format>Maintain the exact same formatting and structure as the original.</format>
  <output>Return ONLY the complete updated itinerary — no preamble, no explanation, no commentary.</output>
</instructions>"""
