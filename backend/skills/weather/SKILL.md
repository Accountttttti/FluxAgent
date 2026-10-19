---
name: weather
description: Get current weather and forecasts for a city.
---

# Weather

Use wttr.in, a free service that needs no API key.

## Current conditions

```bash
curl -s "https://wttr.in/{city}?format=3"
```

## Today's weather (use this single request for questions about today)

```bash
curl -s "https://wttr.in/{city}?1&m"
```

## Full forecast

```bash
curl -s "https://wttr.in/{city}?T&m"
```

Replace `{city}` with the actual city. URL-encode spaces as `+` (e.g. `New+York`).

Tips:
- Units: add `?m` for metric, `?u` for USCS.
- Airport codes work too: `JFK`, `LHR`.
