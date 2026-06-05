# SCPA Scraper Service

This service extracts normalized job postings from static HTML and public job
JSON feeds. It is intentionally small and latency-aware: the request path uses
`httpx` to fetch a URL, BeautifulSoup to parse static HTML, and schema adapters
to normalize JSON job APIs. It does not import the pipeline service.

## Endpoints

### `GET /health`

Returns service status and parser type.

### `POST /scrape/html`

Parses HTML already supplied by a caller.

Request:

```json
{
  "html": "<article class='job-card'><h2>Master of Ceremony</h2></article>",
  "source_url": "https://example.test/jobs",
  "limit": 25
}
```

Response fields:

- `count`: number of extracted jobs.
- `jobs`: normalized job objects.
- `deduplicated`: duplicate cards skipped by title/company/location hash.

Each job contains `title`, `description`, `company`, `location`, `tags`,
`source_url`, and `content_hash`.

### `POST /scrape/url`

Fetches an HTML or JSON URL with `httpx` and parses it with the same extraction
logic.

Request:

```json
{
  "url": "https://example.test/jobs",
  "limit": 25
}
```

The fetch timeout is bounded to 8 seconds. Non-HTML and non-JSON responses
return `415`. Network and HTTP failures return `502`.

### `GET /sample`

Returns parsed sample records for local smoke testing.

### `POST /scrape/run`

Runs one configured scrape cycle. Set `SCRAPER_SEED_URLS` to a comma-separated
list of Indonesia-focused job-board/search result URLs or public job API URLs. The endpoint
fetches each page/feed, extracts job cards, deduplicates them, and returns
normalized records. By default the service uses Kalibrr Indonesia:

```powershell
$env:SCRAPER_SEED_URLS='https://www.kalibrr.com/home/te/indonesia'
$env:SCRAPER_INDONESIA_ONLY='true'
```

If live sources are blocked or return no valid jobs, it falls back to `/sample`
so the continual-training loop can still be validated locally. Set
`SCRAPER_SAMPLE_ONLY=true` to force deterministic sample output.

## Extraction logic

The HTML parser looks for common job card selectors such as:

- `[data-job]`
- `.job`
- `.job-card`
- `.job-listing`
- `.vacancy`
- `article`
- `li`

Within each card it extracts common title, company, location, description, and
tag selectors. All text is whitespace-normalized. Duplicates are removed using
a stable SHA-256 hash of normalized title, company, and location.

The JSON adapter supports common public job API fields including `jobs`,
`results`, `data`, `items`, `title`, `company_name`, `company`, `location`,
`candidate_required_location`, `url`, `source_url`, `company_logo`,
`company_logo_url`, `tags`, and `skills`.

The service also reads Next.js `__NEXT_DATA__` payloads for sources such as
Kalibrr and filters results through Indonesia locality checks by default.

## Latency choices

- Static HTML and JSON feed parsing only in the API request path.
- No browser process is started by default.
- URL fetches use an 8 second timeout and a small response parser.
- `limit` is capped at 100 to avoid large response payloads.

## Limitations

- Dynamic JavaScript-only pages may require a separate Playwright/Selenium batch job.
- The selector strategy is generic and may need source-specific adapters.
- The service does not bypass anti-bot controls or authenticated job boards.
- The output is a cleaned extraction result, not a full canonical pipeline
  normalization pass.
