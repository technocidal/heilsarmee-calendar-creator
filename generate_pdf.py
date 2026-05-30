#!/usr/bin/env python3
"""
Scrapes events from the public Heilsarmee Leipzig calendar and renders
a print-ready PDF per month using FullCalendar.

Run:  python3 generate_pdf.py [OPTIONS]
Out:  <out-dir>/<YYYY-MM> Kalender.pdf
"""

import argparse
import json
import math
import os
import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# ── Constants ─────────────────────────────────────────────────────────────────

BASE_URL         = "https://www.heilsarmee.de"
DEFAULT_LIST_PATH = "/leipzig/termineveranstaltungen.html"
FULLCALENDAR_CDN  = "https://cdn.jsdelivr.net/npm/fullcalendar@6.1.20/index.global.min.js"

PAPER_SIZES = {
    "A3": dict(w=1587, h=1123, font_title=15, font_header=10, font_day=9,  font_event=8),
    "A4": dict(w=1123, h=794,  font_title=13, font_header=8.5, font_day=7, font_event=7),
}

GERMAN_MONTHS = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]

# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    current_month = datetime.today().strftime("%Y-%m")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)

    p.add_argument("--paper",       choices=PAPER_SIZES, default="A3",
                   help="Paper size (default: A3)")
    p.add_argument("--font-title",  type=float, metavar="PT",
                   help="Title font size in pt (overrides paper default)")
    p.add_argument("--font-header", type=float, metavar="PT",
                   help="Column header font size in pt (overrides paper default)")
    p.add_argument("--font-day",    type=float, metavar="PT",
                   help="Day number font size in pt (overrides paper default)")
    p.add_argument("--font-event",  type=float, metavar="PT",
                   help="Event text font size in pt (overrides paper default)")

    p.add_argument("--list-path",   default=DEFAULT_LIST_PATH, metavar="PATH",
                   help=f"URL path to the event list (default: {DEFAULT_LIST_PATH})")
    p.add_argument("--out-dir",     default=os.environ.get("OUT_DIR", "output"), metavar="DIR",
                   help="Output directory (default: output)")

    p.add_argument("--start",       default=current_month, metavar="YYYY-MM",
                   help="First month to generate (default: current month)")
    p.add_argument("--end",         metavar="YYYY-MM",
                   help="Last month to generate (default: same as --start)")

    p.add_argument("--no-time",     action="store_true",
                   help="Don't show event times")
    p.add_argument("--no-title",    action="store_true",
                   help="Don't show the month title")
    p.add_argument("--title",       metavar="TEXT",
                   help="Title text (default: German month name + year, e.g. 'August 2026')")

    return p.parse_args()


def build_config(args: argparse.Namespace) -> dict:
    paper = PAPER_SIZES[args.paper]
    return {
        "paper_name":  args.paper,
        "paper":       paper,
        "fonts": {
            "title":  args.font_title  or paper["font_title"],
            "header": args.font_header or paper["font_header"],
            "day":    args.font_day    or paper["font_day"],
            "event":  args.font_event  or paper["font_event"],
        },
        "list_path":   args.list_path,
        "out_dir":     args.out_dir,
        "start":       args.start,
        "end":         args.end or args.start,
        "show_time":   not args.no_time,
        "show_title":  not args.no_title,
        "title":   args.title,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def months_in_range(start: str, end: str) -> list[str]:
    cur = datetime.strptime(start, "%Y-%m")
    end_dt = datetime.strptime(end, "%Y-%m")
    months = []
    while cur <= end_dt:
        months.append(cur.strftime("%Y-%m"))
        cur = cur.replace(month=cur.month + 1) if cur.month < 12 else cur.replace(year=cur.year + 1, month=1)
    return months


def format_title(month: str, title: str | None) -> str:
    if title is not None:
        return title
    dt = datetime.strptime(month, "%Y-%m")
    return f"{GERMAN_MONTHS[dt.month - 1]} {dt.year}"


# ── Scraping ──────────────────────────────────────────────────────────────────

def fetch_page(list_path: str, page_num: int) -> BeautifulSoup:
    params = {"view": "list"}
    if page_num > 1:
        params["page_e"] = page_num
    r = requests.get(BASE_URL + list_path, params=params, timeout=15)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


def total_pages(soup: BeautifulSoup) -> int:
    nums = [
        int(a.text.strip())
        for a in soup.select(".pagination__link a")
        if a.text.strip().isdigit()
    ]
    return max(nums) if nums else 1


def parse_events(soup: BeautifulSoup, show_time: bool) -> list[dict]:
    events = []
    for row in soup.select(".listing-row--event"):
        time_el = row.select_one("time")
        if not time_el:
            continue
        dt    = time_el.get("datetime", "")
        title = (row.select_one(".listing-row__headline") or row).get_text(strip=True)
        if show_time:
            m = re.search(r"(\d{2}:\d{2})", time_el.get_text(strip=True))
            if m:
                title = f"{m.group(1)} {title}"
        events.append({"start": dt, "title": title, "month": dt[:7]})
    return events


def scrape_events(cfg: dict) -> list[dict]:
    print("→ Scraping events…")
    first = fetch_page(cfg["list_path"], 1)
    pages = total_pages(first)
    all_events = parse_events(first, cfg["show_time"])
    for p in range(2, pages + 1):
        all_events.extend(parse_events(fetch_page(cfg["list_path"], p), cfg["show_time"]))
        print(f"\r  {len(all_events)} events ({p}/{pages} pages)", end="", flush=True)
    print()
    return all_events


# ── HTML template ─────────────────────────────────────────────────────────────

# Placeholders: __CDN__ __CSS__ __TITLE__ __DATE__ __EVENTS__
CALENDAR_TEMPLATE = """\
<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8">
  <script src="__CDN__"></script>
  <style>
__CSS__
  </style>
</head>
<body>
  <div id="page">
    <h1 id="cal-title">__TITLE__</h1>
    <div id="cal"></div>
  </div>
  <script>
    document.addEventListener('DOMContentLoaded', () => {
      const cal = new FullCalendar.Calendar(document.getElementById('cal'), {
        initialView:         'dayGridMonth',
        initialDate:         '__DATE__',
        locale:              'de',
        firstDay:            1,
        timeZone:            'Europe/Berlin',
        events:              __EVENTS__,
        height:              '100%',
        fixedWeekCount:      false,
        dayMaxEvents:        false,
        eventDisplay:        'block',
        showNonCurrentDates: false,
        headerToolbar:       false,
        dayHeaderFormat:     { weekday: 'long' },
        eventContent: function(arg) {
          const m = arg.event.title.match(/^([0-9]{2}:[0-9]{2}) ([^]*)/);
          const div = document.createElement('div');
          if (m) {
            const t = document.createElement('strong');
            t.className = 'ev-time';
            t.textContent = m[1];
            div.appendChild(t);
            div.appendChild(document.createTextNode('\u00a0' + m[2]));
          } else {
            div.textContent = arg.event.title;
          }
          return { domNodes: [div] };
        },
      });
      cal.render();

      // Hide any pill whose bottom edge is clipped by the cell boundary,
      // so we only ever show complete pills — never partial ones.
      setTimeout(() => {
        document.querySelectorAll('.fc-daygrid-day').forEach(day => {
          const eventsEl = day.querySelector('.fc-daygrid-day-events');
          if (!eventsEl) return;
          const limit = eventsEl.getBoundingClientRect().bottom;
          eventsEl.querySelectorAll('.fc-daygrid-event-harness').forEach(h => {
            const pill = h.querySelector('.fc-daygrid-event') || h;
            if (pill.getBoundingClientRect().bottom > limit + 1) {
              h.style.visibility = 'hidden';
            }
          });
        });
      }, 100);
    });
  </script>
</body>
</html>"""


def build_css(fonts: dict, show_title: bool) -> str:
    title_extra = "display: none;" if not show_title else ""
    return f"""\
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    html, body              {{ width: 100%; height: 100%; background: #fff; }}
    #page                   {{ display: flex; flex-direction: column;
                              height: 100vh; padding: 3mm 8mm; gap: 1mm; }}
    #cal-title              {{ text-align: center; color: #c8102e;
                              font-size: {fonts['title']}pt; {title_extra} }}
    #cal                    {{ flex: 1 1 auto; min-height: 0; }}
    .fc-col-header-cell-cushion   {{ font-weight: bold; font-size: {fonts['header']}pt; }}
    .fc-daygrid-day-number        {{ font-size: {fonts['day']}pt; }}
    .fc-day-today                 {{ background: transparent !important; }}
    .fc-daygrid-event             {{ background: #00486a; border-color: #00486a;
                                    white-space: normal !important; }}
    .fc-event-title               {{ font-size: {fonts['event']}pt;
                                    white-space: normal !important; }}
    .fc-daygrid-day-events        {{ overflow: hidden; }}
    .ev-time                      {{ font-weight: bold; }}"""


def calendar_html(cfg: dict, events_json: str, month: str) -> str:
    return (
        CALENDAR_TEMPLATE
        .replace("__CDN__",    FULLCALENDAR_CDN)
        .replace("__CSS__",    build_css(cfg["fonts"], cfg["show_title"]))
        .replace("__TITLE__",  format_title(month, cfg["title"]))
        .replace("__DATE__",   f"{month}-01")
        .replace("__EVENTS__", events_json)
    )


# ── PDF rendering ─────────────────────────────────────────────────────────────

def render_month(pw_page, cfg: dict, events_json: str, month: str) -> bytes:
    paper = cfg["paper"]
    w, h  = paper["w"], paper["h"]
    html  = calendar_html(cfg, events_json, month)

    # Pass 1: render at paper dimensions
    pw_page.set_viewport_size({"width": w, "height": h})
    pw_page.set_content(html, wait_until="networkidle")
    pw_page.wait_for_timeout(500)

    # Measure how much height the calendar content actually needs vs what's available
    rendered_h, cal_h = pw_page.evaluate("""(() => {
        const cal  = document.getElementById('cal');
        const rows = [...cal.querySelectorAll('.fc-daygrid-body tr')];
        if (!rows.length) return [cal.clientHeight, cal.clientHeight];
        let neededBodyH = 0;
        for (const row of rows) {
            const cells = [...row.querySelectorAll('td')];
            if (cells.length) neededBodyH += Math.max(...cells.map(c => c.scrollHeight));
        }
        const body    = cal.querySelector('.fc-daygrid-body');
        const nonBody = cal.clientHeight - (body ? body.clientHeight : 0);
        return [Math.round(nonBody + neededBodyH), cal.clientHeight];
    })()""")

    pdf_opts = dict(
        format=cfg["paper_name"], landscape=True, print_background=True,
        margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
    )

    if rendered_h <= cal_h:
        return pw_page.pdf(**pdf_opts)

    # Pass 2: widen viewport so scaled-down content still fills the full width
    scale       = cal_h / rendered_h
    wider_w     = math.ceil(w / scale)
    final_scale = w / wider_w
    pw_page.set_viewport_size({"width": wider_w, "height": h})
    pw_page.set_content(html, wait_until="networkidle")
    pw_page.wait_for_timeout(500)
    return pw_page.pdf(scale=final_scale, **pdf_opts)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    cfg    = build_config(parse_args())
    months = months_in_range(cfg["start"], cfg["end"])

    events = scrape_events(cfg)
    events_json = json.dumps(
        [{"title": e["title"], "start": e["start"]} for e in events],
        ensure_ascii=False,
    )

    print(f"→ Rendering {len(months)} month(s): {', '.join(months)}")
    os.makedirs(cfg["out_dir"], exist_ok=True)
    with sync_playwright() as pw:
        paper   = cfg["paper"]
        browser = pw.chromium.launch()
        page    = browser.new_page(viewport={"width": paper["w"], "height": paper["h"]})
        for month in months:
            filename = f"{month} Kalender.pdf"
            with open(os.path.join(cfg["out_dir"], filename), "wb") as f:
                f.write(render_month(page, cfg, events_json, month))
            print(f"  ✓ {filename}")
        browser.close()
    print(f"✓ Saved → {cfg['out_dir']}/")


if __name__ == "__main__":
    main()
