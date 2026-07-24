# Econ Calendar API

A standalone economic calendar data service. Fetches economic events —
releases, indicators, and scheduled announcements — from ForexFactory's
public JSON feed, with automatic fallback to Finnhub if that feed is
unavailable. Built for public distribution on RapidAPI.

This service contains no trading logic — it only fetches, normalizes, caches,
and serves calendar data.

## Features

- **Data source with fallback**: ForexFactory's public JSON feed as the
  primary source, Finnhub as a fallback if ForexFactory is unreachable.
- **Caching**: Results are cached in Redis with a configurable TTL, keyed by
  date range, to avoid hammering upstream sources.
- **Impact classification**: Events are classified by impact level (high,
  medium, low, holiday) using the upstream source's own classification — all
  levels and currencies are exposed and filterable, none are hardcoded out.
- **RapidAPI integration**: Verifies the RapidAPI proxy secret on every
  request and identifies callers for per-user rate limiting.
- **Tiered rate limiting**: Atomic, Redis-backed monthly quotas per
  consumer — Free (50/mo), Basic (1,000/mo), Pro (10,000/mo),
  Business (100,000/mo).
- **Auto-generated OpenAPI docs** at `/docs` and `/redoc`.

## API

| Endpoint | Description |
|---|---|
| `GET /v1/calendar` | Full calendar, all impact levels and currencies, paginated |
| `GET /v1/calendar/high-impact` | High-impact events only, paginated |
| `GET /v1/calendar/today` | Today's events |
| `GET /v1/calendar/currency/{code}` | Events filtered by currency code, paginated |
| `GET /health` | Liveness check |

Common query parameters on the paginated endpoints: `page`, `page_size`,
`impact` (repeatable), `currency`, `from_date`, `to_date`. See `/docs` for
full parameter documentation.

## Setup

### Requirements

- Python 3.12+
- Redis (for caching and rate limiting)

### Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Configure

Copy `.env.example` to `.env` and fill in values:

```bash
cp .env.example .env
```

| Variable | Description | Default |
|---|---|---|
| `RAPIDAPI_PROXY_SECRET` | Shared secret RapidAPI sends on every proxied request. If unset, the check is skipped (local dev). | unset |
| `FOREXFACTORY_BASE_URL` | Base URL for the ForexFactory JSON feed. | `https://nfs.faireconomy.media` |
| `FINNHUB_API_KEY` | API key for the Finnhub fallback. If unset, fallback is disabled. | unset |
| `FINNHUB_BASE_URL` | Base URL for the Finnhub API. | `https://finnhub.io/api/v1` |
| `HTTP_TIMEOUT_SECONDS` | Timeout for upstream HTTP requests. | `10` |
| `CACHE_TTL_SECONDS` | How long fetched calendar data is cached. | `900` |
| `REDIS_URL` | Redis connection URL. | `redis://localhost:6379/0` |
| `RATE_LIMIT_FREE` | Monthly request limit, Free tier. | `50` |
| `RATE_LIMIT_BASIC` | Monthly request limit, Basic tier. | `1000` |
| `RATE_LIMIT_PRO` | Monthly request limit, Pro tier. | `10000` |
| `RATE_LIMIT_BUSINESS` | Monthly request limit, Business tier. | `100000` |

### Run locally

Start Redis (e.g. `redis-server` or `docker run -p 6379:6379 redis`), then:

```bash
uvicorn app.main:app --reload
```

Or use the startup script:

```bash
./start.sh
```

Visit `http://localhost:8000/docs` for interactive API docs.

Without `RAPIDAPI_PROXY_SECRET` set, the auth check is skipped, so you can
call the API directly while developing. `X-RapidAPI-User` and
`X-RapidAPI-Subscription` headers are optional locally too — omitting them
falls back to your client IP as the rate-limit key and the Free tier.

## Deployment

1. Build and run with Docker:

   ```bash
   docker build -t econ-calendar-api .
   docker run -p 8000:8000 --env-file .env econ-calendar-api
   ```

   Point `REDIS_URL` at a reachable Redis instance (a managed Redis add-on,
   or a Redis container on the same network).

2. Or deploy directly with `start.sh` on any host with Python 3.12+ and
   Redis reachable, setting environment variables as documented above.

3. On RapidAPI, set the origin URL to your deployed service, and configure
   `RAPIDAPI_PROXY_SECRET` to match the secret shown in your RapidAPI
   provider dashboard.

## RapidAPI integration notes

- Every request is expected to carry `X-RapidAPI-Proxy-Secret`, verified
  against `RAPIDAPI_PROXY_SECRET`. Requests missing or failing this check
  receive `403 Forbidden`.
- `X-RapidAPI-User` identifies the calling consumer for rate limiting.
- `X-RapidAPI-Subscription` indicates the consumer's plan tier (`FREE`,
  `BASIC`, `PRO`, `BUSINESS`); unrecognized or missing values default to
  `FREE`.
- Requests over a consumer's monthly limit receive `429 Too Many Requests`
  with a JSON body describing the limit and current usage.
