"""Historical race-day weather lookup via Open-Meteo (free, no API key).

Open-Meteo exposes two hourly-temperature endpoints we use:
  - archive-api.open-meteo.com/v1/archive : ERA5 reanalysis, deep history back
    to 1940, but with a multi-day ingest delay so it lacks the last few days.
  - api.open-meteo.com/v1/forecast?past_days=N : covers the recent past (up to
    92 days) including today, so it fills the archive's trailing gap.

A race's weather is immutable once run, so callers cache a successful result
forever. Two failure modes are kept distinct so the caller can cache correctly:
  - genuinely unavailable (bad input / no data for the date) -> returns None;
    the caller caches a permanent "unavailable" marker and never retries.
  - transient (network error, HTTP 429/5xx from Open-Meteo, which throttles
    bursts especially from shared CI IPs) -> raises WeatherLookupError after
    retries; the caller leaves it uncached so the next sync retries it.
"""
import datetime
import time
from typing import Dict, Optional

import requests

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
# Within this many days of today the ERA5 archive may not have ingested the
# date yet, so use the forecast endpoint's past_days window instead.
RECENT_DAYS = 10
REQUEST_TIMEOUT = 30
# Retry transient failures (throttling/network) with growing backoff so a burst
# of race lookups recovers within a single sync instead of caching a bad null.
RETRY_BACKOFF_SECONDS = (2, 5, 12)


class WeatherLookupError(Exception):
    """Transient failure reaching Open-Meteo; the lookup should be retried."""


def _today_utc() -> datetime.date:
    return datetime.datetime.now(datetime.timezone.utc).date()


def fetch_race_temperature(
    lat: float,
    lng: float,
    local_date: str,
    local_hour: int,
    *,
    today: Optional[datetime.date] = None,
    attempts: int = 2,
    sleep=time.sleep,
) -> Optional[Dict]:
    """Return {"temp_f", "feels_f"} for a location/date/hour.

    Returns None when the lookup is genuinely unavailable (bad input, or a 200
    response with no usable temperature). Raises WeatherLookupError when every
    attempt fails transiently (network / HTTP error) so the caller can retry on
    a later sync rather than caching a permanent null.

    local_date is "YYYY-MM-DD" in the activity's local timezone; local_hour is
    0-23 local. We request with timezone=auto so Open-Meteo returns hourly
    timestamps already in the location's local time, letting us match the race
    start hour directly with no timezone arithmetic.
    """
    if lat is None or lng is None or not local_date:
        return None
    try:
        race_day = datetime.date.fromisoformat(local_date)
    except ValueError:
        return None

    age_days = ((today or _today_utc()) - race_day).days

    params = {
        "latitude": lat,
        "longitude": lng,
        "hourly": "temperature_2m,apparent_temperature",
        "temperature_unit": "fahrenheit",
        "timezone": "auto",
    }
    if 0 <= age_days <= RECENT_DAYS:
        url = FORECAST_URL
        params["past_days"] = min(max(age_days + 1, 1), 92)
        params["forecast_days"] = 1
    else:
        url = ARCHIVE_URL
        params["start_date"] = local_date
        params["end_date"] = local_date

    data = None
    last_err = None
    for attempt in range(attempts):
        try:
            resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            break
        except (requests.RequestException, ValueError) as exc:
            last_err = exc
            if attempt < attempts - 1:
                sleep(RETRY_BACKOFF_SECONDS[min(attempt, len(RETRY_BACKOFF_SECONDS) - 1)])
    if data is None:
        raise WeatherLookupError(f"Open-Meteo request failed after {attempts} attempts: {last_err}")

    hourly = data.get("hourly") or {}
    times = hourly.get("time") or []
    temps = hourly.get("temperature_2m") or []
    feels = hourly.get("apparent_temperature") or []
    if not times or not temps:
        return None

    target = f"{local_date}T{int(local_hour):02d}:00"
    if target in times:
        idx = times.index(target)
    else:
        # Fall back to the same-date hour closest to the race start hour.
        candidates = [
            (abs(int(t[11:13]) - int(local_hour)), j)
            for j, t in enumerate(times)
            if t.startswith(local_date) and len(t) >= 13 and t[11:13].isdigit()
        ]
        if not candidates:
            return None
        idx = min(candidates)[1]

    temp_f = temps[idx] if idx < len(temps) else None
    feels_f = feels[idx] if idx < len(feels) else None
    if temp_f is None:
        return None
    return {
        "temp_f": round(float(temp_f), 1),
        "feels_f": round(float(feels_f), 1) if feels_f is not None else None,
    }
