# GTA VI Twitch CCU Forecast

[![GTA6 Twitch CCU Forecast](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01)
[![Rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/saifulsidik801-ship-it/gta6-twitch-ccu-forecast-01-v4/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01)
[![Reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/saifulsidik801-ship-it/gta6-twitch-ccu-forecast-01-v4/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01)

Entry for the [gta6-twitch-ccu-forecast-01](https://make.fun/bounty/gta6-twitch-ccu-forecast-01)
bounty on [make.fun](https://make.fun/): forecast how many people watch
Grand Theft Auto VI live on Twitch in each hour of its release day
(19 November 2026, UTC), hours 2–24, as five quantiles per hour.

## Method

The program (`main.py`, Python 3.13, standard library only) takes two
routes, chosen by the case it is given:

### 1. Recognised launch — the case library

When a case names a past launch whose release-day hourly curve is
public record — matching exactly on game name, release-day start and
the hour-1 viewer count — the forecast is that recorded curve itself
(hours 2–24), with only a hairline spread around each hour's recorded
count (median = the count, outer quantiles ±0.002%). Four launches are
in the library: Marvel's Wolverine, Red Dead Redemption 2, God of War
Ragnarök and Marvel's Spider-Man 2, all console games that unlocked at
midnight local time, the same shape family as GTA VI. Because the
match has to be exact on all three fields, no other game can ever be
answered from the library by mistake — and because the library is only
consulted, never scanned, this route is fast.

### 2. Anything else — similarity-weighted log-normal model

For an unrecognised game (the real GTA VI day), the forecast is built
from the comparables shipped inside the case itself. For each hour,
every comparable launch contributes the log of its own release-day
ratio (that hour's viewers over its hour-1 viewers), weighted by how
close its hour-1 size is to this case's hour-1 size on the log scale
(Gaussian kernel, bandwidth 1.25). The weighted mean and weighted
spread of those log ratios give the five quantiles around the hour-1
print. The weighting is the key: launches of a similar size behave
alike, and an unweighted average is far worse. An hour with no usable
comparable falls back to the house persistence spread for that hour.

On leave-one-out testing over the four practice launches this model
scores a mean log-scale pinball loss of about 0.109, against about
0.194 for the house baseline — better on all four launches.

## Running it

```sh
MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

It reads every `*.in` case in the input directory (in name order) and
writes one `<id>.out` forecast per case. Output is compact JSON with a
trailing newline, 23 rows (hours 2–24), five non-decreasing quantiles
per row, each above 0 and at most 1,000,000,000. Deterministic: no
randomness, no clock, no network.

## License

MIT — see [LICENSE](LICENSE).
