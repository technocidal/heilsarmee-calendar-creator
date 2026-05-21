# Heilsarmee Leipzig Calendar PDF Generator

Scrapes the public event list from [heilsarmee.de/leipzig](https://www.heilsarmee.de/leipzig/termineveranstaltungen.html?view=list) and renders a print-ready **landscape A4 PDF** — one page per month — styled to match the site's calendar, using [FullCalendar](https://fullcalendar.io).

## Usage

```bash
make run
```

Builds the Docker image, generates the PDF and opens it. Output: `output/termine-heilsarmee-leipzig.pdf`

## How it works

1. **Scrape** — `requests` + `BeautifulSoup` fetch all paginated upcoming events from the public list view (no login required)
2. **Render** — each month is rendered as a FullCalendar `dayGridMonth` page inside a headless Chromium (Playwright), styled to match the site's colours (`#c8102e` red, `#00486a` teal)
3. **Shrink-to-fit** — if a dense month overflows A4 height, a second render pass widens the viewport so the scaled-down content still fills the full page width
4. **Merge** — individual month PDFs are merged into one with `pypdf`

## Requirements

- Docker
