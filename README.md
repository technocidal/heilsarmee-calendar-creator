# Heilsarmee Leipzig Calendar PDF Generator

Scrapes the public event list from [heilsarmee.de/leipzig](https://www.heilsarmee.de/leipzig/termineveranstaltungen.html?view=list) and renders **one print-ready A3 landscape PDF per month** using FullCalendar.

## Usage

```bash
# Build and run (opens output folder)
mise all

# Just build the Docker image
mise build

# Run with custom options
mise all -- --start 2026-08 --end 2026-09 --title "Sommer"
```

Output: `output/<YYYY-MM> Kalender.pdf`

## How it works

1. **Scrape** — `requests` + `BeautifulSoup` fetch all paginated upcoming events from the public list view (no login required)
2. **Render** — each month is rendered as a FullCalendar `dayGridMonth` page inside a headless Chromium (Playwright), styled to match the site's colours (`#c8102e` red, `#00486a` teal)
3. **Shrink-to-fit** — if a dense month overflows A3 height, a second render pass widens the viewport so the scaled-down content still fills the full page width
4. **Save** — individual month PDFs are saved with names like `2026-05 Kalender.pdf`

## Requirements

- Docker
- [Mise](https://mise.jdx.dev) (optional, for `mise all`/`mise build`)

## CLI Options

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

## CI/CD

Codeberg Actions builds and pushes the Docker image on every push to `main`.
