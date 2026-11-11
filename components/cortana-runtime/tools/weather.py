"""get_weather — live conditions and forecast.

This is the one tool that reaches the public internet. Everything else in
Cortana is local-only, so it's worth being explicit: this calls wttr.in,
sending only the city name. No API key, no account, no telemetry, and no
personal data leaves the machine. If you'd rather Cortana never touch the
network at all, delete this file from tools/ and drop `weather` from
core/tools_loader.py — nothing else depends on it.
"""

import urllib.parse

import httpx

from core.tool_registry import tool
from core.permissions import RiskLevel

WTTR = "https://wttr.in/{place}?format=j1"
TIMEOUT = 8.0


def _describe(current: dict) -> str:
    desc = (current.get("weatherDesc") or [{}])[0].get("value", "").strip()
    return desc or "conditions unknown"


def get_weather(city: str = "", days: int = 1) -> dict:
    place = urllib.parse.quote((city or "").strip())  # empty = geo-IP guess
    url = WTTR.format(place=place)

    try:
        resp = httpx.get(url, timeout=TIMEOUT, headers={"User-Agent": "curl/8"})
    except httpx.TimeoutException:
        return {"error": "The weather service didn't respond in time. Try again in a moment."}
    except Exception as e:
        return {"error": f"Couldn't reach the weather service ({type(e).__name__}). Are you online?"}

    if resp.status_code != 200:
        return {"error": f"Weather service returned {resp.status_code} for '{city or 'your location'}'."}

    try:
        data = resp.json()
        current = data["current_condition"][0]
        area = (data.get("nearest_area") or [{}])[0]
        place_name = (area.get("areaName") or [{}])[0].get("value", city or "your location")
        region = (area.get("country") or [{}])[0].get("value", "")
    except Exception:
        return {"error": "The weather service sent something unreadable."}

    result = {
        "location": f"{place_name}{', ' + region if region else ''}",
        "temperature_c": current.get("temp_C"),
        "feels_like_c": current.get("FeelsLikeC"),
        "conditions": _describe(current),
        "humidity_pct": current.get("humidity"),
        "wind_kmph": current.get("windspeedKmph"),
        "observed_at": current.get("localObsDateTime"),
    }

    n = max(1, min(int(days or 1), 3))
    forecast = []
    for day in data.get("weather", [])[:n]:
        hourly = day.get("hourly") or []
        midday = hourly[len(hourly) // 2] if hourly else {}
        forecast.append(
            {
                "date": day.get("date"),
                "min_c": day.get("mintempC"),
                "max_c": day.get("maxtempC"),
                "conditions": _describe(midday) if midday else "",
                "chance_of_rain_pct": midday.get("chanceofrain") if midday else None,
            }
        )
    result["forecast"] = forecast
    return result


tool(
    name="get_weather",
    description=(
        "Get current weather and a short forecast for a city. Use whenever the "
        "user asks about weather, temperature, or rain. Omit city to use the "
        "current location. This is the only tool that uses the internet."
    ),
    risk=RiskLevel.LOW,
    parameters={
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "City name, e.g. 'Delhi'. Omit for current location."},
            "days": {"type": "integer", "description": "Forecast days, 1-3 (default 1)."},
        },
        "required": [],
    },
)(get_weather)
