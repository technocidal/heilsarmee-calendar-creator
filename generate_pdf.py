#!/usr/bin/env python3
"""
generate_pdf.py
Scrapes all upcoming events from the public Heilsarmee Leipzig calendar
and renders a print-ready landscape A4 PDF using FullCalendar — one page per month.

Run:  python3 generate_pdf.py
Out:  termine-heilsarmee-leipzig.pdf
"""

import io
import json
import math
import os
import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from pypdf import PdfReader, PdfWriter

BASE_URL  = "https://www.heilsarmee.de"
LIST_PATH = "/leipzig/termineveranstaltungen.html"
OUT_FILE  = os.environ.get("OUT_FILE", "termine-heilsarmee-leipzig.pdf")

# ── Scraping ──────────────────────────────────────────────────────────────────

def fetch_page(page_num: int) -> BeautifulSoup:
    params = {"view": "list"}
    if page_num > 1:
        params["page_e"] = page_num
    r = requests.get(BASE_URL + LIST_PATH, params=params, timeout=15)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")

def total_pages(soup: BeautifulSoup) -> int:
    nums = [
        int(a.text.strip())
        for a in soup.select(".pagination__link a")
        if a.text.strip().isdigit()
    ]
    return max(nums) if nums else 1

def parse_events(soup: BeautifulSoup) -> list[dict]:
    events = []
    for row in soup.select(".listing-row--event"):
        time_el = row.select_one("time")
        if not time_el:
            continue
        dt        = time_el.get("datetime", "")
        time_text = time_el.get_text(strip=True)  # e.g. "22.05.2026 10:00–13:00"
        title     = (row.select_one(".listing-row__headline") or row).get_text(strip=True)

        # Extract start time e.g. "10:00" from "22.05.2026 10:00–13:00"
        m = re.search(r'(\d{2}:\d{2})', time_text)
        time_part = m.group(1) if m else ""

        events.append({
            "start": dt,
            "title": f"{time_part} {title}" if time_part else title,
            "month": dt[:7],  # "YYYY-MM"
        })
    return events

def scrape_all_events() -> list[dict]:
    print("→ Scraping events…")
    first      = fetch_page(1)
    pages      = total_pages(first)
    all_events = parse_events(first)
    for p in range(2, pages + 1):
        all_events.extend(parse_events(fetch_page(p)))
        print(f"\r  {len(all_events)} events ({p}/{pages} pages)", end="", flush=True)
    print()
    return all_events

def active_months(events: list[dict]) -> list[str]:
    return sorted({e["month"] for e in events})

# ── FullCalendar HTML template ────────────────────────────────────────────────

FULLCALENDAR_CDN = "https://cdn.jsdelivr.net/npm/fullcalendar@6.1.20/index.global.min.js"

# Plain string — no f-string so JavaScript braces need no escaping.
# Placeholders: __CDN__  __DATE__  __EVENTS__
CALENDAR_TEMPLATE = """\
<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8">
  <script src="__CDN__"></script>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    html, body { width: 100%; height: 100%; background: #fff; }
    #cal { padding: 3mm 8mm 3mm; height: 100vh; }

    .fc-toolbar-title           { color: #c8102e; font-size: 13pt; }
    .fc-toolbar.fc-header-toolbar { margin-bottom: 2px !important; }
    .fc-daygrid-event           { background: #00486a; border-color: #00486a;
                                  white-space: normal !important; }
    .fc-event-title             { font-size: 7pt; white-space: normal !important; }
    .fc-day-today               { background: transparent !important; }
    .fc-col-header-cell-cushion { font-weight: bold; font-size: 8.5pt; }
    .ev-time                    { font-weight: bold; }
    .ev-content                 { display: block; }
    .fc-daygrid-day-events      { overflow: hidden; }
  </style>
</head>
<body>
  <div id="cal"></div>
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
        headerToolbar:       { left: '', center: 'title', right: '' },
        dayHeaderFormat:     { weekday: 'long' },
        eventContent: function(arg) {
          const m = arg.event.title.match(/^([0-9]{2}:[0-9]{2}) ([^]*)/);
          const div = document.createElement('div');
          div.className = 'ev-content';
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

      // After layout: hide any pill whose bottom edge is clipped by the cell
      // boundary, so we only ever show complete pills — never partial ones.
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

def calendar_html(events_json: str, initial_date: str) -> str:
    return (
        CALENDAR_TEMPLATE
        .replace("__CDN__",    FULLCALENDAR_CDN)
        .replace("__DATE__",   initial_date)
        .replace("__EVENTS__", events_json)
    )

# ── PDF rendering ─────────────────────────────────────────────────────────────

# A4 landscape at 96 dpi
A4_W_PX = 1123
A4_H_PX = 794

def render_month(pw_page, events_json: str, month: str) -> bytes:
    html = calendar_html(events_json, f"{month}-01")

    # Pass 1: render at standard A4 width
    pw_page.set_viewport_size({"width": A4_W_PX, "height": A4_H_PX})
    pw_page.set_content(html, wait_until="networkidle")
    pw_page.wait_for_timeout(500)
    rendered_h = pw_page.evaluate("""
        (() => {
          const cal  = document.getElementById('cal');
          const rows = [...cal.querySelectorAll('.fc-daygrid-body tr')];
          if (!rows.length) return cal.clientHeight;
          // Sum the actual needed height of each row
          // (scrollHeight of a cell reflects full content even when clipped)
          let neededBodyH = 0;
          for (const row of rows) {
            const cells = [...row.querySelectorAll('td')];
            if (cells.length) neededBodyH += Math.max(...cells.map(c => c.scrollHeight));
          }
          const body    = cal.querySelector('.fc-daygrid-body');
          const nonBody = cal.clientHeight - (body ? body.clientHeight : 0);
          return Math.round(nonBody + neededBodyH);
        })()
    """)

    if rendered_h <= A4_H_PX:
        # Fits without scaling — export directly
        return pw_page.pdf(
            format="A4", landscape=True, print_background=True,
            margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
        )

    # Pass 2: widen the viewport by 1/scale so scaled content fills full A4 width
    scale   = A4_H_PX / rendered_h
    wider_w = math.ceil(A4_W_PX / scale)
    # final_scale = A4_W_PX / wider_w ensures width fits exactly;
    # height also fits because wider columns reduce wrapping (rendered_h2 ≤ rendered_h)
    final_scale = A4_W_PX / wider_w
    pw_page.set_viewport_size({"width": wider_w, "height": A4_H_PX})
    pw_page.set_content(html, wait_until="networkidle")
    pw_page.wait_for_timeout(500)
    return pw_page.pdf(
        format="A4", landscape=True, print_background=True, scale=final_scale,
        margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
    )

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    events  = scrape_all_events()
    months  = active_months(events)
    print(f"✓ {len(events)} events across {len(months)} months: {', '.join(months)}")

    fc_events   = [{"title": e["title"], "start": e["start"]} for e in events]
    events_json = json.dumps(fc_events, ensure_ascii=False)
    print("→ Rendering PDF…")
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": A4_W_PX, "height": A4_H_PX})

        os.makedirs(os.path.dirname(OUT_FILE) or ".", exist_ok=True)

        # Save individual month PDFs
        for month in months:
            print(f"  {month}…")
            filename = f"{month} Kalender.pdf"
            with open(
                os.path.join(os.path.dirname(OUT_FILE) or ".", filename), "wb"
            ) as f:
                f.write(render_month(page, events_json, month))
            print(f"  ✓ {filename}")
        browser.close()
    print(f"✓ Saved → {len(months)} PDFs in {os.path.dirname(OUT_FILE) or '.'}")
