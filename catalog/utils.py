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
        9:00a.m.-5:00p.m.   -> 09:00am-05:00pm
        9:00am-5:00pm       -> 09:00am-05:00pm
        2:00-4:00p.m.       -> 02:00pm-04:00pm
        2:00-4:00am         -> 02:00am-04:00am
        12:00am-12:00pm     -> 00:00am-12:00pm
        10-6pm              -> 10:00am-06:00pm   ✅ fixed
    """

    def normalize_single_time(t: str, default_ampm: str = "") -> str:
        """
        Normalize a single time string:
        - Remove dots and spaces from am/pm
        - Add missing am/pm if needed (using default_ampm)
        - Convert hour to 2 digits
        """
        t = re.sub(r"[\.\s]", "", t.lower())

        ampm = ""
        if t.endswith("am"):
            ampm = "am"
            t = t[:-2]
        elif t.endswith("pm"):
            ampm = "pm"
            t = t[:-2]

        if not ampm and default_ampm:
            ampm = default_ampm

        if ":" in t:
            h, m = t.split(":")
        else:
            h, m = t, "00"

        h = int(h)
        m = int(m)

        if h == 12 and ampm == "am":
            h = 0

        return f"{h:02d}:{m:02d}{ampm}"

    parts = re.split(r"[-–]", time_range)
    if len(parts) != 2:
        return time_range

    start_raw, end_raw = parts[0].strip(), parts[1].strip()

    # First normalize end, so we know its am/pm
    norm_end = normalize_single_time(end_raw)

    # Determine default am/pm for start:
    # if end is pm and start has no am/pm → assume am
    default_ampm = "am" if norm_end.endswith("pm") else "pm"
    norm_start = normalize_single_time(start_raw, default_ampm)

    return f"{norm_start}-{norm_end}"


def get_open_close_time(time_range: str):
    if "," in time_range:
        times = time_range.split(",")
        open_time = times[0].strip().split("-")[0]
        close_time = times[-1].strip().split("-")[-1]
        open_time, close_time = normalize_ampm(
            f"{open_time}-{close_time}").split("-")
    else:
        open_time, close_time = normalize_ampm(time_range.strip()).split("-")
    return to_24h(open_time), to_24h(close_time)


def get_start_end_day(time_range: str):
    """
    Extracts the start and end day from a given time range string.
    """

    return get_open_close_time(time_range)
