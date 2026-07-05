import argparse
import os
import re
from typing import Any, Dict, List

from activity_types import canonicalize_activity_type, featured_types_from_config, normalize_activity_type
from provider_fields import (
    coalesce as _shared_coalesce,
    get_nested as _shared_get_nested,
    pick_duration_seconds as _shared_pick_duration_seconds,
)
from utils import ensure_dir, load_config, normalize_source, parse_iso_datetime, raw_activity_dir, read_json, write_json

OUT_PATH = os.path.join("data", "activities_normalized.json")
RACE_BEST_EFFORTS_PATH = os.path.join("data", "race_best_efforts.json")
RACE_HEARTRATE_PATH = os.path.join("data", "race_heartrate.json")
RACE_WEATHER_PATH = os.path.join("data", "race_weather.json")
RACE_SPLITS_PATH = os.path.join("data", "race_splits.json")
# The final split of a race is included as a full "mile" only when it covers at
# least this fraction of a mile (drops a 5K's 0.1 and a 10K's 0.2, keeps a
# ~4-miler's 0.8). Pace is always normalized per mile, so a partial still shows
# a true per-mile pace.
PARTIAL_MILE_MIN = 0.75
_METERS_PER_MILE = 1609.344

_RACE_NAME_RE = re.compile(
    r"\b(race|races|5k|10k|15k|half|marathon|miler|milers|dash|trot|solstice)\b",
    re.IGNORECASE,
)
_BADGE_TO_STRAVA_EFFORT = {
    "5K":       "5k",
    "10K":      "10k",
    "Half":     "Half-Marathon",
    "Marathon": "Marathon",
}


def _race_badge_label_mi(dist_mi: float) -> str:
    if 2.9  <= dist_mi <= 3.4:  return "5K"
    if 3.7  <= dist_mi <= 4.2:  return "4 Mi"
    if 4.9  <= dist_mi <= 5.3:  return "5 Mi"
    if 6.0  <= dist_mi <= 6.6:  return "10K"
    if 9.8  <= dist_mi <= 10.4: return "10 Mi"
    if 11.7 <= dist_mi <= 12.4: return "12 Mi"
    if 13.0 <= dist_mi <= 13.5: return "Half"
    if 26.0 <= dist_mi <= 26.5: return "Marathon"
    return ""


def _extract_strava_pr_rank(dist_meters: float, best_efforts: List[Dict]) -> int:
    dist_mi = dist_meters * 0.000621371
    effort_name = _BADGE_TO_STRAVA_EFFORT.get(_race_badge_label_mi(dist_mi))
    if not effort_name:
        return 0
    effort_name_lower = effort_name.lower()
    for effort in (best_efforts or []):
        if str(effort.get("name") or "").lower() == effort_name_lower:
            rank = effort.get("pr_rank")
            if rank in (1, 2, 3):
                return int(rank)
    return 0


def _mile_paces_from_splits(splits: Any) -> List[int]:
    """Per-mile pace (whole seconds/mile), indexed by mile, from raw splits.

    Each split is {"dist_m", "moving_s", ...}. All splits are full miles except
    possibly the last; the final split is included only when it covers at least
    PARTIAL_MILE_MIN of a mile. Pace is normalized per mile (moving_s / miles),
    so a partial final split still yields a comparable per-mile pace.
    """
    if not isinstance(splits, list) or not splits:
        return []
    paces: List[int] = []
    last_idx = len(splits) - 1
    for i, s in enumerate(splits):
        if not isinstance(s, dict):
            continue
        dist_m = s.get("dist_m")
        moving_s = s.get("moving_s")
        if not dist_m or not moving_s:
            continue
        miles = float(dist_m) / _METERS_PER_MILE
        # Tolerance absorbs the 0.1m rounding of dist_m so an exactly-0.75-mile
        # final split is inclusive (matches "at least 0.75").
        if i == last_idx and miles < PARTIAL_MILE_MIN - 1e-4:
            continue
        if miles <= 0:
            continue
        paces.append(round(float(moving_s) / miles))
    return paces


def _coalesce(*values: Any) -> Any:
    return _shared_coalesce(*values)


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _pick_duration_seconds(*values: Any) -> float:
    return _shared_pick_duration_seconds(*values)


def _duration_candidates(activity: Dict[str, Any]) -> List[Any]:
    return [
        activity.get("moving_time"),
        activity.get("movingDuration"),
        activity.get("duration"),
        activity.get("elapsedDuration"),
        activity.get("elapsed_time"),
        activity.get("elapsedTime"),
        _get_nested(activity, ["summaryDTO", "movingDuration"]),
        _get_nested(activity, ["summaryDTO", "duration"]),
        _get_nested(activity, ["summaryDTO", "elapsedDuration"]),
        _get_nested(activity, ["activitySummary", "movingDuration"]),
        _get_nested(activity, ["activitySummary", "duration"]),
        _get_nested(activity, ["activitySummary", "elapsedDuration"]),
    ]


def _get_nested(payload: Dict[str, Any], keys: List[str]) -> Any:
    return _shared_get_nested(payload, keys)


def _resolve_canonical_type(raw_value: str, source: str) -> str:
    return canonicalize_activity_type(raw_value, source=source)


def _normalize_activity(activity: Dict, type_aliases: Dict[str, str], source: str) -> Dict:
    activity_id = _coalesce(activity.get("id"), activity.get("activityId"))
    start_date_local = activity.get("start_date_local") or activity.get("start_date")
    if not activity_id or not start_date_local:
        return {}

    dt = parse_iso_datetime(str(start_date_local).replace(" ", "T"))
    date_str = dt.strftime("%Y-%m-%d")
    year = dt.year

    raw_activity_type = str(
        _coalesce(
            activity.get("type"),
            _get_nested(activity, ["activityType", "typeKey"]),
            _get_nested(activity, ["activityTypeDTO", "typeKey"]),
            activity.get("activityType"),
            "Unknown",
        )
    )
    raw_type = str(activity.get("sport_type") or raw_activity_type or "Unknown")
    canonical_raw_type = _resolve_canonical_type(raw_type, source)
    activity_type = type_aliases.get(raw_type, type_aliases.get(canonical_raw_type, canonical_raw_type))
    distance = _coalesce(activity.get("distance"), activity.get("totalDistance"))
    moving_time = _pick_duration_seconds(*_duration_candidates(activity))
    elevation_gain = _coalesce(
        activity.get("total_elevation_gain"),
        activity.get("elevationGain"),
        activity.get("totalElevationGain"),
    )
    activity_name = str(_coalesce(activity.get("name"), activity.get("activityName"), "") or "").strip()
    workout_type = activity.get("workout_type")
    is_race = workout_type == 1 or bool(_RACE_NAME_RE.search(activity_name))

    normalized = {
        "id": str(activity_id),
        "start_date_local": str(start_date_local).replace(" ", "T"),
        "date": date_str,
        "year": year,
        "raw_activity_type": raw_activity_type,
        "raw_type": raw_type,
        "type": activity_type,
        "distance": _safe_float(distance),
        "moving_time": _safe_float(moving_time),
        "elevation_gain": _safe_float(elevation_gain),
    }
    if activity_name:
        normalized["name"] = activity_name
    if is_race:
        normalized["is_race"] = True
    return normalized


def _load_existing() -> Dict[str, Dict]:
    if not os.path.exists(OUT_PATH):
        return {}
    try:
        existing_items = read_json(OUT_PATH)
    except Exception:
        return {}
    existing: Dict[str, Dict] = {}
    for item in existing_items or []:
        if not isinstance(item, dict):
            continue
        activity_id = item.get("id")
        if activity_id is None:
            continue
        existing[str(activity_id)] = item
    return existing


def normalize() -> List[Dict]:
    config = load_config()
    source = normalize_source(config.get("source", "strava"))
    activities_cfg = config.get("activities", {}) or {}
    type_aliases = activities_cfg.get("type_aliases", {}) or {}
    featured_types = featured_types_from_config(activities_cfg)
    include_all_types = bool(activities_cfg.get("include_all_types", True))
    exclude_types = {str(item) for item in (activities_cfg.get("exclude_types", []) or [])}
    exclude_race_ids = {str(item) for item in (activities_cfg.get("exclude_race_ids", []) or [])}
    group_other_types = bool(activities_cfg.get("group_other_types", True))
    other_bucket = str(activities_cfg.get("other_bucket", "OtherSports"))
    group_aliases = activities_cfg.get("group_aliases", {}) or {}
    featured_set = set(featured_types)

    # In CI, activities/raw is ephemeral per run, so keep persisted normalized
    # history and overlay any newly fetched raw activities.
    existing = _load_existing()

    raw_dirs = [raw_activity_dir(source)]
    # Backward compatibility for old Strava layout (activities/raw/*.json).
    legacy_raw_dir = os.path.join("activities", "raw")
    if source == "strava" and os.path.isdir(legacy_raw_dir):
        raw_dirs.append(legacy_raw_dir)

    for current_raw_dir in raw_dirs:
        if not os.path.exists(current_raw_dir):
            continue
        for filename in sorted(os.listdir(current_raw_dir)):
            if not filename.endswith(".json"):
                continue
            path = os.path.join(current_raw_dir, filename)
            if not os.path.isfile(path):
                continue
            activity = read_json(path)
            normalized = _normalize_activity(activity, type_aliases, source)
            if not normalized:
                continue
            normalized_type = normalize_activity_type(
                normalized.get("type"),
                featured_types=featured_types,
                group_other_types=group_other_types,
                other_bucket=other_bucket,
                group_aliases=group_aliases,
            )
            normalized["type"] = normalized_type
            if normalized_type in exclude_types:
                continue
            if not include_all_types and normalized_type not in featured_set:
                continue
            existing[str(normalized["id"])] = normalized

    items = [
        item
        for item in existing.values()
        if item.get("id") is not None and item.get("date")
    ]
    race_best_efforts: Dict[str, List] = {}
    if os.path.exists(RACE_BEST_EFFORTS_PATH):
        try:
            race_best_efforts = read_json(RACE_BEST_EFFORTS_PATH) or {}
        except Exception:
            pass

    race_heartrate: Dict[str, Dict] = {}
    if os.path.exists(RACE_HEARTRATE_PATH):
        try:
            race_heartrate = read_json(RACE_HEARTRATE_PATH) or {}
        except Exception:
            pass

    race_weather: Dict[str, Dict] = {}
    if os.path.exists(RACE_WEATHER_PATH):
        try:
            race_weather = read_json(RACE_WEATHER_PATH) or {}
        except Exception:
            pass

    race_splits: Dict[str, List] = {}
    if os.path.exists(RACE_SPLITS_PATH):
        try:
            race_splits = read_json(RACE_SPLITS_PATH) or {}
        except Exception:
            pass

    for item in items:
        if str(item.get("id") or "") in exclude_race_ids:
            item.pop("is_race", None)
            item.pop("strava_pr_rank", None)
            continue
        if "is_race" not in item:
            activity_name = str(item.get("name") or "").strip()
            if _RACE_NAME_RE.search(activity_name):
                item["is_race"] = True
        if item.get("is_race"):
            activity_id = str(item.get("id") or "")
            efforts = race_best_efforts.get(activity_id, [])
            pr_rank = _extract_strava_pr_rank(float(item.get("distance") or 0), efforts)
            if pr_rank:
                item["strava_pr_rank"] = pr_rank
            elif "strava_pr_rank" in item:
                del item["strava_pr_rank"]
            hr_entry = race_heartrate.get(activity_id) or {}
            avg_hr = hr_entry.get("avg") if isinstance(hr_entry, dict) else None
            if avg_hr:
                item["avg_hr"] = round(float(avg_hr))
            elif "avg_hr" in item:
                del item["avg_hr"]
            # Real race-day ambient temperature from the weather service
            # (Open-Meteo), already in °F; keyed by activity id.
            wx = race_weather.get(activity_id) or {}
            temp_f = wx.get("temp_f") if isinstance(wx, dict) else None
            if temp_f is not None:
                item["avg_temp_f"] = round(float(temp_f))
            elif "avg_temp_f" in item:
                del item["avg_temp_f"]
            # Per-mile pace (seconds/mile), indexed by mile. Drops a too-short
            # final partial split (see PARTIAL_MILE_MIN).
            mile_paces = _mile_paces_from_splits(race_splits.get(activity_id))
            if mile_paces:
                item["mile_paces"] = mile_paces
            elif "mile_paces" in item:
                del item["mile_paces"]
        raw_activity_type = str(item.get("raw_activity_type") or item.get("raw_type") or item.get("type") or other_bucket)
        raw_type = str(item.get("raw_type") or raw_activity_type or other_bucket)
        item["raw_activity_type"] = raw_activity_type
        item["raw_type"] = raw_type
        canonical_raw_type = _resolve_canonical_type(raw_type, source)
        source_type = type_aliases.get(raw_type, type_aliases.get(canonical_raw_type, canonical_raw_type))
        item["type"] = normalize_activity_type(
            source_type,
            featured_types=featured_types,
            group_other_types=group_other_types,
            other_bucket=other_bucket,
            group_aliases=group_aliases,
        )
    if exclude_types:
        items = [item for item in items if item.get("type") not in exclude_types]
    if not include_all_types:
        items = [item for item in items if item.get("type") in featured_set]
    items.sort(key=lambda x: (x["date"], x["id"]))
    return items


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize raw activities")
    parser.parse_args()

    ensure_dir("data")
    items = normalize()
    write_json(OUT_PATH, items)
    print(f"Wrote {len(items)} normalized activities")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
