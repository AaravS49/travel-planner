import datetime
import requests

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

WMO_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Foggy", 48: "Icy fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
    77: "Snow grains",
    80: "Slight showers", 81: "Moderate showers", 82: "Violent showers",
    85: "Slight snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with heavy hail",
}


def _get_coordinates(city: str) -> tuple[float, float, str] | None:
    try:
        r = requests.get(GEOCODING_URL, params={"name": city, "count": 1, "language": "en"}, timeout=5)
        r.raise_for_status()
        results = r.json().get("results")
        if not results:
            return None
        result = results[0]
        return result["latitude"], result["longitude"], result.get("country", "")
    except Exception:
        return None


def _get_forecast(lat: float, lon: float, start_date: datetime.date, end_date: datetime.date) -> list[dict] | None:
    try:
        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,weathercode,windspeed_10m_max",
            "timezone": "auto",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }
        r = requests.get(FORECAST_URL, params=params, timeout=5)
        r.raise_for_status()
        data = r.json().get("daily", {})
        days = []
        for i, date_str in enumerate(data.get("time", [])):
            days.append({
                "date": date_str,
                "condition": WMO_CODES.get(data["weathercode"][i], "Unknown"),
                "temp_high": data["temperature_2m_max"][i],
                "temp_low": data["temperature_2m_min"][i],
                "precipitation_mm": data["precipitation_sum"][i],
                "wind_kmh": data["windspeed_10m_max"][i],
            })
        return days
    except Exception:
        return None


def trip_within_forecast_window(start_date: datetime.date) -> bool:
    return (start_date - datetime.date.today()).days <= 7


def get_trip_weather(destinations: list[str], start_date: datetime.date, end_date: datetime.date) -> dict[str, list[dict]]:
    """Returns a dict mapping each destination to its daily forecast list. Skips cities that fail lookup."""
    results = {}
    for city in destinations:
        coords = _get_coordinates(city)
        if not coords:
            continue
        lat, lon, _ = coords
        forecast = _get_forecast(lat, lon, start_date, end_date)
        if forecast:
            results[city] = forecast
    return results


def format_weather_for_prompt(weather: dict[str, list[dict]]) -> str:
    """Formats fetched weather data into an XML block for injection into the prompt."""
    if not weather:
        return ""

    lines = ["<weather_forecast>"]
    for city, days in weather.items():
        lines.append(f"  <city name=\"{city}\">")
        for day in days:
            rain_note = f", {day['precipitation_mm']}mm precipitation" if day["precipitation_mm"] > 0 else ""
            lines.append(
                f"    <day date=\"{day['date']}\">"
                f"{day['condition']}, "
                f"{day['temp_low']}°C–{day['temp_high']}°C, "
                f"wind {day['wind_kmh']} km/h"
                f"{rain_note}"
                f"</day>"
            )
        lines.append("  </city>")
    lines.append("</weather_forecast>")
    return "\n".join(lines)
