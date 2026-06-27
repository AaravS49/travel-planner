import os
import json
import datetime
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from google import genai
from prompts import build_trip_context, build_itinerary_prompt, build_refine_prompt
from weather import trip_within_forecast_window, get_trip_weather, format_weather_for_prompt
from budget import extract_budget

load_dotenv()

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
MODEL = "gemini-2.5-flash"

app = FastAPI()


class TripRequest(BaseModel):
    destinations: list[str]
    start_date: str
    end_date: str
    adults: int = 1
    children: int = 0
    children_ages: str = ""
    elderly: int = 0
    currency: str = "USD"
    budget_min: int = 1000
    budget_max: int = 5000
    dietary: list[str] = []
    mobility: list[str] = []
    fitness: str = "Moderate"
    other_restrictions: str = ""
    must_dos: str = ""
    general_interests: str = ""


class RefineRequest(BaseModel):
    itinerary: str
    chat_history: list[dict] = []
    user_request: str


class BudgetRequest(BaseModel):
    itinerary: str
    currency: str


@app.post("/api/generate")
def generate(req: TripRequest):
    start_date = datetime.date.fromisoformat(req.start_date)
    end_date = datetime.date.fromisoformat(req.end_date)

    trip_context = build_trip_context(
        destinations=req.destinations,
        start_date=start_date,
        end_date=end_date,
        adults=req.adults,
        children=req.children,
        children_ages=req.children_ages,
        elderly=req.elderly,
        currency=req.currency,
        budget_min=req.budget_min,
        budget_max=req.budget_max,
        dietary=req.dietary,
        mobility=req.mobility,
        fitness=req.fitness,
        other_restrictions=req.other_restrictions,
        must_dos=req.must_dos,
        general_interests=req.general_interests,
    )

    weather_context = ""
    weather_loaded = False
    if trip_within_forecast_window(start_date):
        weather_data = get_trip_weather(req.destinations, start_date, end_date)
        weather_context = format_weather_for_prompt(weather_data)
        weather_loaded = bool(weather_context)

    prompt = build_itinerary_prompt(trip_context, req.currency, req.fitness, weather_context)

    def stream():
        yield f"data: {json.dumps({'type': 'weather', 'loaded': weather_loaded})}\n\n"
        for chunk in client.models.generate_content_stream(model=MODEL, contents=prompt):
            if chunk.text:
                yield f"data: {json.dumps({'type': 'chunk', 'text': chunk.text})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.post("/api/refine")
def refine(req: RefineRequest):
    prompt = build_refine_prompt(
        current_itinerary=req.itinerary,
        chat_history=req.chat_history,
        user_request=req.user_request,
    )

    def stream():
        for chunk in client.models.generate_content_stream(model=MODEL, contents=prompt):
            if chunk.text:
                yield f"data: {json.dumps({'type': 'chunk', 'text': chunk.text})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.post("/api/budget")
def budget(req: BudgetRequest):
    data = extract_budget(client, MODEL, req.itinerary, req.currency)
    return {"data": data}


app.mount("/", StaticFiles(directory="static", html=True), name="static")
