import json
import re


def to_12h(time_str: str) -> str:
    """
    Convert a 24-hour time string to 12-hour format with am/pm.

    Examples:
        "09:00"  -> "9:00am"
        "12:00"  -> "12:00pm"
        "00:00"  -> "12:00am"
        "13:30"  -> "1:30pm"
        "23:15:05" -> "11:15:05pm"
    """
    if not time_str:
        return ""

    t = re.sub(r"\s", "", time_str)

    m = re.fullmatch(r"(\d{1,2}):(\d{2})(?::(\d{2}))?", t)
    if not m:
        raise ValueError("Time must be in HH:MM or HH:MM:SS 24-hour format")

    h = int(m.group(1))
    mi = int(m.group(2))
    s = m.group(3)
    si = int(s) if s is not None else None

    # basic validation
    if not (0 <= h <= 23 and 0 <= mi <= 59 and (si is None or 0 <= si <= 59)):
        raise ValueError("Invalid time components")

    ampm = "am" if h < 12 else "pm"
    h12 = h % 12
    if h12 == 0:
        h12 = 12

    return f"{h12}:{mi:02d}{ampm}"


def to_24h(time_str: str) -> str:
    """
    Convert a time string in 12-hour format with am/pm to 24-hour format.

    Examples:
        9:00am   -> 09:00
        12:00pm  -> 12:00
        12:00am  -> 00:00
        1:30pm   -> 13:30
    """

    # Remove dots and spaces (e.g. "a.m." -> "am")
    t = re.sub(r"[\.\s]", "", time_str.lower())

    # Extract am/pm
    ampm = ""
    if t.endswith("am"):
        ampm = "am"
        t = t[:-2]
    elif t.endswith("pm"):
        ampm = "pm"
        t = t[:-2]
    else:
        raise ValueError("Time must specify am or pm")

    # Split hours and minutes
    if ":" in t:
        h, m = t.split(":")
    else:
        h, m = t, "00"

    h = int(h)
    m = int(m)

    # Convert to 24h format
    if ampm == "am":
        if h == 12:  # 12am -> 00
            h = 0
    elif ampm == "pm":
        if h != 12:  # 1pm-11pm -> +12
            h += 12

    return f"{h:02d}:{m:02d}"


def normalize_ampm(time_range: str) -> str:
    """
    Normalize a time range string with am/pm into a standard format.

    Examples:
        9:00a.m.-5:00p.m. -> 09:00am-05:00pm
        9:00am-5:00pm     -> 09:00am-05:00pm
        2:00-4:00p.m.     -> 02:00pm-04:00pm
        2:00-4:00am       -> 02:00am-04:00am
        12:00am-12:00pm   -> 12:00am-12:00pm
        10-6pm            -> 10:00am-06:00pm
        12-1pm            -> 12:00pm-01:00pm
        11-1am            -> 11:00pm-01:00am
        11pm-1            -> 11:00pm-01:00am
    """

    def parse_time_token(token: str) -> dict:
        raw = token
        token = re.sub(r"[\.\s]", "", token.lower())

        match = re.fullmatch(r"(\d{1,2})(?::(\d{1,2}))?(am|pm)?", token)
        if not match:
            raise ValueError(f"Invalid time token: {raw!r}")

        hour = int(match.group(1))
        minute = int(match.group(2) or "00")
        ampm = match.group(3)

        if not 1 <= hour <= 12:
            raise ValueError(f"Hour out of range in {raw!r}: {hour}")
        if not 0 <= minute <= 59:
            raise ValueError(f"Minute out of range in {raw!r}: {minute}")

        return {
            "hour": hour,
            "minute": minute,
            "ampm": ampm,
        }

    def infer_start_ampm(start: dict, end: dict) -> str:
        end_ampm = end["ampm"]
        start_hour = start["hour"]
        end_hour = end["hour"]

        if end_ampm == "pm":
            if start_hour == 12:
                return "pm"
            return "am" if start_hour > end_hour else "pm"

        if end_ampm == "am":
            if start_hour == 12:
                return "am"
            return "pm" if start_hour > end_hour else "am"

        return ""

    def infer_end_ampm(start: dict, end: dict) -> str:
        start_ampm = start["ampm"]
        start_hour = start["hour"]
        end_hour = end["hour"]

        if start_ampm == "am":
            if end_hour == 12:
                return "pm"
            return "pm" if end_hour < start_hour else "am"

        if start_ampm == "pm":
            if end_hour == 12:
                return "am"
            return "am" if end_hour < start_hour else "pm"

        return ""

    def format_time(token: dict) -> str:
        return f"{token['hour']:02d}:{token['minute']:02d}{token['ampm'] or ''}"

    parts = re.split(r"\s*[-–]\s*", time_range.strip(), maxsplit=1)
    if len(parts) != 2:
        return time_range

    start = parse_time_token(parts[0])
    end = parse_time_token(parts[1])

    if start["ampm"] is None and end["ampm"] is not None:
        start["ampm"] = infer_start_ampm(start, end)
    elif end["ampm"] is None and start["ampm"] is not None:
        end["ampm"] = infer_end_ampm(start, end)

    return f"{format_time(start)}-{format_time(end)}"


def get_open_close_time(time_range: str):
    if "," in time_range:
        times = time_range.split(",")
        open_time = times[0].strip().split("-")[0]
        close_time = times[-1].strip().split("-")[-1]
        open_time, close_time = normalize_ampm(f"{open_time}-{close_time}").split("-")
    else:
        open_time, close_time = normalize_ampm(time_range.strip()).split("-")
    return to_24h(open_time), to_24h(close_time)


def get_start_end_day(time_range: str):
    """
    Extracts the start and end day from a given time range string.
    """

    return get_open_close_time(time_range)


DAY_NAMES = {
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
}

SPECIAL_VALUES = {
    "open 24 hours",
    "closed",
}


def _is_special_value(value: str) -> bool:
    return value.strip().lower() in SPECIAL_VALUES


def _is_time_range(value: str) -> bool:
    value = value.strip()
    return bool(
        re.fullmatch(
            r"\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)?\s*[-–]\s*"
            r"\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)?",
            value,
            flags=re.IGNORECASE,
        )
    )


def _collapse_intervals(values: list[str]) -> str:
    values = [v.strip() for v in values if v and v.strip()]
    if not values:
        return ""

    if len(values) == 1:
        return values[0]

    if _is_special_value(values[0]):
        return values[0]

    interval_values = [v for v in values if _is_time_range(v)]
    if len(interval_values) != len(values):
        return values[0]

    first_parts = re.split(r"\s*[-–]\s*", interval_values[0], maxsplit=1)
    last_parts = re.split(r"\s*[-–]\s*", interval_values[-1], maxsplit=1)

    if len(first_parts) != 2 or len(last_parts) != 2:
        return values[0]

    start_time = first_parts[0].strip()
    end_time = last_parts[1].strip()

    return f"{start_time}-{end_time}"


def _normalize_day_value(value):
    if value is None:
        return ""

    if isinstance(value, str):
        value = value.strip()
        if not value:
            return ""
        return value

    if isinstance(value, list):
        return _collapse_intervals([str(item).strip() for item in value])

    return str(value).strip()


def _repair_broken_working_hours(raw: str) -> dict:
    tokens = re.findall(r'"([^"]+)"', raw)
    if not tokens:
        raise ValueError(f"Could not parse working_hours: {raw!r}")

    result = {}
    current_day = None
    values = []

    def flush():
        nonlocal current_day, values
        if current_day is not None:
            result[current_day] = _collapse_intervals(values)
        current_day = None
        values = []

    for token in tokens:
        token = token.strip()

        if token in DAY_NAMES:
            flush()
            current_day = token
        else:
            if current_day is None:
                raise ValueError(f"Value found before day name: {token!r} in {raw!r}")
            values.append(token)

    flush()
    return result


def parse_working_hours(value: str) -> dict:
    value = (value or "").strip()
    if not value:
        return {}

    try:
        data = json.loads(value)
    except json.JSONDecodeError:
        return _repair_broken_working_hours(value)

    if not isinstance(data, dict):
        raise ValueError(
            f"working_hours must be a JSON object, got {type(data).__name__}"
        )

    return {
        str(day).strip(): _normalize_day_value(hours) for day, hours in data.items()
    }
