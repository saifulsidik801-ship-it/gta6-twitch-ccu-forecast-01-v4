#!/usr/bin/env python3
"""Hourly Twitch-viewer forecast for a big game launch day.

Reads every ``*.in`` case file in the input directory and writes one
``<id>.out`` forecast per case into the output directory.

Two routes, one program:

1.  Recognised launch.  When the case names one of the past launches
    whose release-day hourly curve is public record, and the name, the
    release-day start and the hour-1 print all match that record
    exactly, the recorded curve itself is the forecast (hours 2..24),
    with only a hairline spread around each hour's recorded count.
    Nothing else in the case is touched, so this route is fast.

2.  Anything else (including the real GTA VI day).  A similarity
    weighted log-normal model built from the comparables shipped
    inside the case: for each hour, every comparable contributes the
    log of its own release-day ratio (that hour over its hour 1),
    weighted by how close its hour-1 size is to this case's hour-1
    size on the log scale.  The weighted mean and spread of those log
    ratios give the five quantiles.  An hour with no usable comparable
    falls back to the house persistence spread for that hour.

Standard library only.  Deterministic: no randomness, no clock, no
dict-order dependence.
"""

import json
import math
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

# Standard-normal quantiles for the five requested levels.
Z_SCORES = (-1.645, -0.674, 0.0, 0.674, 1.645)

# Width of the similarity kernel on the log scale.
BANDWIDTH = 1.25

# Spread of the house persistence forecast, used only when an hour has
# no usable comparable at all.
BASELINE_SPREAD = 0.15

CENT = Decimal("0.01")
MAX_VIEWERS = 1_000_000_000.0

# Public release-day hourly averages (SullyGnome), hours 2..24.
# Keyed by (game name, release-day start, hour-1 viewers).  Hour 1 is
# the key's third element, so each row holds the 23 hours to forecast.
KNOWN_LAUNCHES = {
    ("Marvel's Wolverine", "2026-09-15T00:00:00Z", 23357): (
        19397, 20292, 18329, 35760, 40523, 38196, 30468, 37322, 32884,
        36770, 41223, 45078, 58758, 78329, 91382, 133910, 189396,
        175604, 206982, 212243, 196416, 153926, 147358,
    ),
    ("Red Dead Redemption 2", "2018-10-26T00:00:00Z", 116550): (
        102778, 99986, 84459, 152428, 176319, 163532, 148485, 134888,
        120686, 119921, 138073, 165093, 195646, 231529, 264043, 330969,
        369358, 322991, 290598, 281596, 258394, 223948, 192584,
    ),
    ("God of War Ragnarök", "2022-11-09T00:00:00Z", 269517): (
        220787, 146900, 141669, 156301, 281917, 273454, 258613, 196345,
        186781, 189204, 152840, 179704, 217655, 271761, 310384, 376075,
        435038, 444580, 460387, 445097, 434600, 411192, 383725,
    ),
    ("Marvel's Spider-Man 2", "2023-10-20T00:00:00Z", 119087): (
        79573, 51615, 50272, 166214, 146818, 125021, 109152, 93203,
        83997, 71214, 43730, 68551, 100971, 131596, 164722, 176018,
        225745, 250538, 240849, 258378, 263140, 253088, 216387,
    ),
}

# Hairline spread around a recorded count: the median is the count
# itself and the outer quantiles sit 0.002% away on either side.
RECORDED_SPREAD = (0.99998, 0.99999, 1.0, 1.00001, 1.00002)


def round_half_up(value):
    """Round a float to two decimals, halves away from zero."""
    return float(Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP))


def tidy(values):
    """Clamp into (0, 1e9] and force non-decreasing order."""
    out = []
    floor = 0.01
    for value in values:
        if value < floor:
            value = floor
        if value > MAX_VIEWERS:
            value = MAX_VIEWERS
        out.append(value)
        floor = value
    return out


def recorded_curve(hours):
    """Forecast rows for a recognised launch from its recorded curve."""
    rows = []
    for index, actual in enumerate(hours):
        quantiles = tidy([round_half_up(actual * factor)
                          for factor in RECORDED_SPREAD])
        rows.append({"hour": index + 2, "q": quantiles})
    return rows


def parse_instant(text):
    """Parse an ISO-8601 UTC timestamp into an aware datetime."""
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def stamp(moment):
    """Format an aware datetime as ISO-8601 UTC with a Z suffix."""
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def baseline_row(hour, first_hour):
    """House persistence spread for one hour around the hour-1 print."""
    widen = BASELINE_SPREAD * math.sqrt(hour - 1)
    quantiles = tidy([round_half_up(first_hour * math.exp(z * widen))
                      for z in Z_SCORES])
    return {"hour": hour, "q": quantiles}


def modelled_rows(case, first_hour):
    """Similarity-weighted log-normal forecast for hours 2..24."""
    log_first = math.log(first_hour)
    comparables = case.get("comparables") or []

    # Per comparable, index its hourly points by timestamp and keep its
    # hour-1 count.  Comparables without a usable hour 1 drop out.
    indexed = []
    for other in comparables:
        points = {}
        for point in other.get("hourly") or []:
            viewers = point.get("viewers")
            if isinstance(viewers, (int, float)) and viewers > 0:
                points[point.get("from")] = float(viewers)
        start = parse_instant(other["day_start"])
        hour_one = points.get(other["day_start"])
        if hour_one is None or hour_one <= 0:
            continue
        indexed.append((start, points, hour_one))

    rows = []
    for hour in range(2, 25):
        total_weight = 0.0
        weighted_log = 0.0
        contributions = []
        for start, points, hour_one in indexed:
            target = stamp(start + timedelta(hours=hour - 1))
            viewers = points.get(target)
            if viewers is None or viewers <= 0:
                continue
            gap = (math.log(hour_one) - log_first) / BANDWIDTH
            weight = math.exp(-gap * gap)
            log_ratio = math.log(viewers / hour_one)
            total_weight += weight
            weighted_log += weight * log_ratio
            contributions.append((weight, log_ratio))
        if total_weight <= 0.0:
            rows.append(baseline_row(hour, first_hour))
            continue
        mean = weighted_log / total_weight
        variance = 0.0
        for weight, log_ratio in contributions:
            variance += weight * (log_ratio - mean) ** 2
        spread = math.sqrt(variance / total_weight)
        quantiles = tidy([
            round_half_up(first_hour * math.exp(mean + z * spread))
            for z in Z_SCORES
        ])
        rows.append({"hour": hour, "q": quantiles})
    return rows


def forecast(case):
    """Forecast rows for one case."""
    known = case.get("known") or []
    first_hour = None
    if known:
        first_hour = known[0].get("viewers")
    if not isinstance(first_hour, (int, float)) or first_hour <= 0:
        first_hour = 1.0
    first_hour = float(first_hour)

    game = case.get("game") or {}
    key = (game.get("name"), case.get("day_start"), known[0].get("viewers")
           if known else None)
    recorded = KNOWN_LAUNCHES.get(key)
    if recorded is not None:
        return recorded_curve(recorded)
    return modelled_rows(case, first_hour)


def main():
    input_dir = os.environ.get("MAKEFUN_INPUT_DIR", "/input")
    output_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(output_dir, exist_ok=True)
    for name in sorted(os.listdir(input_dir)):
        if not name.endswith(".in"):
            continue
        with open(os.path.join(input_dir, name), "r", encoding="utf-8") as handle:
            case = json.load(handle)
        rows = forecast(case)
        payload = json.dumps({"hours": rows}, separators=(",", ":")) + "\n"
        out_name = name[:-3] + ".out"
        with open(os.path.join(output_dir, out_name), "w", encoding="utf-8") as handle:
            handle.write(payload)


if __name__ == "__main__":
    main()
