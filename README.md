# Heilsarmee Leipzig Calendar PDF Generator

Scrapes the public event list from [heilsarmee.de/leipzig](https://www.heilsarmee.de/leipzig/termineveranstaltungen.html?view=list) and renders **one print-ready A3 landscape PDF per month** using FullCalendar.

## Usage

```bash
python3 generate_pdf.py --help
```

- `--paper A3|A4` — paper size (default: A3)
- `--font-title`, `--font-header`, `--font-day`, `--font-event` — override default font sizes
- `--list-path PATH` — URL path to the event list
- `--out-dir DIR` — output directory (default: output)
- `--start YYYY-MM` — first month (default: current month)
- `--end YYYY-MM` — last month (default: same as --start)
- `--no-time` — hide event times
- `--no-title` — hide the month title
- `--title TEXT` — custom title text (default: German month name + year)

## How it works

1. **Scrape** — `requests` + `BeautifulSoup` fetch all paginated upcoming events from the public list view (no login required)
2. **Render** — each month is rendered as a FullCalendar `dayGridMonth` page inside a headless Chromium (Playwright), styled to match the site's colours (`#c8102e` red, `#00486a` teal)
3. **Shrink-to-fit** — if a dense month overflows A3 height, a second render pass widens the viewport so the scaled-down content still fills the full page width
4. **Save** — individual month PDFs are saved with names like `2026-05 Kalender.pdf`

<a href="https://0rwx.com">
    <img src="https://0rwx.com/static/AI-W.png" width="44"/>
</a>
