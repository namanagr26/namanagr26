#!/usr/bin/env python3
"""
Generates self-hosted profile-README graphics (stats.svg, streak.svg,
langs.svg, year.svg) from the GitHub GraphQL API. No third-party image
services -- everything is drawn here and committed straight into the repo
by the accompanying GitHub Action.

Env vars required:
  GITHUB_TOKEN  - a token with read access (the default Actions token is enough
                   for public data)
  GH_LOGIN      - the GitHub username to report on
"""

import base64
import datetime as dt
import os
import sys
import textwrap
import urllib.request
import json

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
GH_LOGIN = os.environ["GH_LOGIN"]
API_URL = "https://api.github.com/graphql"

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(HERE, "fonts")

# ---------------------------------------------------------------------------
# Shared visual language
# ---------------------------------------------------------------------------
BG = "#0d1117"
FG = "#e6edf3"
DIM = "#8b949e"
ACCENT = "#58a6ff"
GRID = "#21262d"
RAMP = " .:-=+*#%@"  # low -> high intensity, single hue, opacity does the work

CHAR_W = 7.74          # advance width in px at font-size 12.9, JetBrains Mono
FONT_SIZE = 12.9
LINE_H = 18


def _read_font_b64(name):
    with open(os.path.join(FONT_DIR, name), "rb") as fh:
        return base64.b64encode(fh.read()).decode()


REGULAR_B64 = _read_font_b64("text-regular.woff2")
BOLD_B64 = _read_font_b64("text-bold.woff2")

FONT_FACE = f"""
    @font-face {{
      font-family: 'JBM';
      src: url(data:font/woff2;base64,{REGULAR_B64}) format('woff2');
      font-weight: 400;
    }}
    @font-face {{
      font-family: 'JBM';
      src: url(data:font/woff2;base64,{BOLD_B64}) format('woff2');
      font-weight: 700;
    }}
    text {{ font-family: 'JBM', monospace; fill: {FG}; }}
    .dim {{ fill: {DIM}; }}
    .accent {{ fill: {ACCENT}; }}
    .b {{ font-weight: 700; }}
"""


def svg_header(width, height, title):
    return textwrap.dedent(f"""\
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}"
             width="{width}" height="{height}" role="img" aria-label="{title}">
          <title>{title}</title>
          <style>{FONT_FACE}</style>
          <rect width="{width}" height="{height}" rx="10" fill="{BG}"/>
    """)


SVG_FOOTER = "</svg>\n"


# ---------------------------------------------------------------------------
# GitHub GraphQL
# ---------------------------------------------------------------------------
def gql(query, variables):
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "profile-readme-generator",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if "errors" in payload:
        raise RuntimeError(payload["errors"])
    return payload["data"]


QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays { date contributionCount }
        }
      }
    }
    repositories(first: 100, privacy: PUBLIC, ownerAffiliations: [OWNER],
                 isFork: false, orderBy: {field: UPDATED_AT, direction: DESC}) {
      nodes {
        name
        languages(first: 5, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""


def fetch():
    now = dt.datetime.now(dt.timezone.utc)
    today = now.date()
    # pin the window to whole UTC days so the graphics are stable run-to-run
    frm = dt.datetime.combine(today - dt.timedelta(days=364), dt.time(0, 0, 0),
                               tzinfo=dt.timezone.utc)
    to = dt.datetime.combine(today, dt.time(23, 59, 59), tzinfo=dt.timezone.utc)
    data = gql(QUERY, {
        "login": GH_LOGIN,
        "from": frm.isoformat(),
        "to": to.isoformat(),
    })
    return data["user"], frm, to


# ---------------------------------------------------------------------------
# Derived stats
# ---------------------------------------------------------------------------
def flatten_days(calendar):
    days = []
    for week in calendar["weeks"]:
        for d in week["contributionDays"]:
            days.append((d["date"], d["contributionCount"]))
    days.sort(key=lambda x: x[0])
    return days


def weekly_totals(days, n_weeks=12):
    weeks = []
    bucket = []
    for date_str, count in days:
        bucket.append(count)
        if len(bucket) == 7:
            weeks.append(sum(bucket))
            bucket = []
    if bucket:
        weeks.append(sum(bucket))
    return weeks[-n_weeks:]


def compute_streaks(days):
    """Longest streak in-window, and current streak ending at the most
    recent day with data (today or yesterday)."""
    longest = 0
    longest_range = (None, None)
    run = 0
    run_start = None
    for date_str, count in days:
        if count > 0:
            if run == 0:
                run_start = date_str
            run += 1
            if run > longest:
                longest = run
                longest_range = (run_start, date_str)
        else:
            run = 0

    current = 0
    current_range = (None, None)
    for date_str, count in reversed(days):
        if count > 0:
            if current == 0:
                current_range = (date_str, date_str)
            current += 1
            current_range = (date_str, current_range[1])
        else:
            break

    return {
        "longest": longest, "longest_range": longest_range,
        "current": current, "current_range": current_range,
    }


def language_stats(repos):
    by_bytes = {}
    by_repo = {}
    colors = {}
    for repo in repos["nodes"]:
        edges = repo["languages"]["edges"]
        if not edges:
            continue
        top_lang = edges[0]["node"]["name"]
        by_repo[top_lang] = by_repo.get(top_lang, 0) + 1
        for e in edges:
            name = e["node"]["name"]
            colors[name] = e["node"]["color"] or ACCENT
            by_bytes[name] = by_bytes.get(name, 0) + e["size"]
    return by_bytes, by_repo, colors


def build_heading_svg(label, width=900):
    """Section heading as SVG -- the only way to put a custom typeface on a
    heading, since GitHub strips <font>/<style>/CSS from markdown text.
    Lowercase mono label with a hairline rule running to the right edge.
    Image headings have no anchor link, so the alt text carries the word
    for screen readers and GitHub's outline."""
    height = 28
    label = label.lower()
    out = textwrap.dedent(f"""\
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}"
             width="{width}" height="{height}" role="img" aria-label="{label}">
          <title>{label}</title>
          <style>{FONT_FACE}</style>
    """)
    text_w = len(label) * CHAR_W
    out += f'<text x="0" y="19" font-size="{FONT_SIZE}" class="dim">{label}</text>\n'
    out += (f'<line x1="{text_w + 12:.1f}" y1="14" x2="{width}" y2="14" '
            f'stroke="{GRID}" stroke-width="1"/>\n')
    out += SVG_FOOTER
    return out


def ramp_char(value, vmax):
    if vmax <= 0:
        return RAMP[0]
    idx = min(len(RAMP) - 1, int((value / vmax) * (len(RAMP) - 1)))
    return RAMP[idx]


# ---------------------------------------------------------------------------
# SVG builders
# ---------------------------------------------------------------------------
def build_stats_svg(total, weekly, frm, to):
    width, height = 480, 160
    bar_w, gap = 24, 8
    max_w = max(weekly) or 1
    chart_x0 = 24
    chart_y0 = 110
    chart_h = 34

    bars = []
    for i, v in enumerate(weekly):
        h = 2 if v == 0 else max(2, (v / max_w) * chart_h)
        x = chart_x0 + i * (bar_w + gap)
        y = chart_y0 - h
        bars.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w}" height="{h:.1f}" '
            f'rx="2" fill="{ACCENT}" opacity="0.85"/>'
        )

    date_range = f'{frm.strftime("%d %b %Y")} \u2192 {to.strftime("%d %b %Y")}'

    out = svg_header(width, height, f"{GH_LOGIN} contribution total")
    out += f'<text x="24" y="40" font-size="30" class="b">{total:,}</text>\n'
    out += f'<text x="24" y="60" font-size="12" class="dim">contributions in the last year</text>\n'
    out += "".join(bars) + "\n"
    out += f'<line x1="24" y1="{chart_y0}" x2="{width-24}" y2="{chart_y0}" stroke="{GRID}"/>\n'
    out += f'<text x="24" y="{chart_y0+18}" font-size="10" class="dim">last 12 weeks, weekly totals</text>\n'
    out += f'<text x="{width-24}" y="{chart_y0+18}" font-size="10" class="dim" text-anchor="end">{date_range}</text>\n'
    out += SVG_FOOTER
    return out


def build_streak_svg(streak_data):
    width, height = 480, 150

    def fmt_range(r):
        a, b = r
        if not a:
            return "\u2014"
        if a == b:
            return dt.datetime.strptime(a, "%Y-%m-%d").strftime("%d %b %Y")
        a_d = dt.datetime.strptime(a, "%Y-%m-%d").strftime("%d %b")
        b_d = dt.datetime.strptime(b, "%Y-%m-%d").strftime("%d %b %Y")
        return f"{a_d} \u2192 {b_d}"

    out = svg_header(width, height, f"{GH_LOGIN} contribution streaks")
    out += '<text x="24" y="36" font-size="12" class="dim">current streak</text>\n'
    out += f'<text x="24" y="66" font-size="30" class="b accent">{streak_data["current"]} days</text>\n'
    out += f'<text x="24" y="86" font-size="11" class="dim">{fmt_range(streak_data["current_range"])}</text>\n'

    out += f'<line x1="24" y1="104" x2="{width-24}" y2="104" stroke="{GRID}"/>\n'

    out += '<text x="24" y="126" font-size="12" class="dim">longest streak</text>\n'
    out += f'<text x="200" y="126" font-size="14" class="b">{streak_data["longest"]} days</text>\n'
    out += f'<text x="330" y="126" font-size="11" class="dim">{fmt_range(streak_data["longest_range"])}</text>\n'
    out += SVG_FOOTER
    return out


def build_langs_svg(by_bytes, by_repo):
    width, height = 480, 220
    top_bytes = sorted(by_bytes.items(), key=lambda kv: kv[1], reverse=True)[:5]
    total_bytes = sum(v for _, v in top_bytes) or 1
    top_repo = sorted(by_repo.items(), key=lambda kv: kv[1], reverse=True)[:5]

    out = svg_header(width, height, f"{GH_LOGIN} top languages")
    out += '<text x="24" y="28" font-size="12" class="dim">top languages · by bytes</text>\n'

    bar_x, bar_w_max = 150, 260
    y = 46
    for name, size in top_bytes:
        pct = size / total_bytes
        bw = max(2, pct * bar_w_max)
        out += f'<text x="24" y="{y+11}" font-size="11">{name}</text>\n'
        out += (f'<rect x="{bar_x}" y="{y}" width="{bar_w_max}" height="10" '
                f'rx="2" fill="{GRID}"/>\n')
        out += (f'<rect x="{bar_x}" y="{y}" width="{bw:.1f}" height="10" '
                f'rx="2" fill="{ACCENT}"/>\n')
        out += (f'<text x="{width-24}" y="{y+9}" font-size="10" '
                f'class="dim" text-anchor="end">{pct*100:.0f}%</text>\n')
        y += 24

    y += 12
    out += f'<line x1="24" y1="{y}" x2="{width-24}" y2="{y}" stroke="{GRID}"/>\n'
    y += 20
    out += f'<text x="24" y="{y}" font-size="12" class="dim">top languages · by repo count</text>\n'
    y += 20
    row = " \u00b7 ".join(f"{n} ({c})" for n, c in top_repo)
    out += f'<text x="24" y="{y}" font-size="11">{row}</text>\n'
    out += SVG_FOOTER
    return out


def build_year_svg(days):
    """GitHub-style calendar, one character per day, single hue, opacity
    carries the intensity (never per-character rainbow)."""
    cell = 11
    pad_left, pad_top = 30, 24
    weeks = [days[i:i + 7] for i in range(0, len(days), 7)]
    width = pad_left + len(weeks) * cell + 20
    height = pad_top + 7 * cell + 30
    vmax = max((c for _, c in days), default=1) or 1

    out = svg_header(width, height, f"{GH_LOGIN} contribution calendar")
    out += f'<text x="{pad_left}" y="16" font-size="11" class="dim">contributions, past year</text>\n'

    for wi, week in enumerate(weeks):
        for di, (date_str, count) in enumerate(week):
            x = pad_left + wi * cell
            y = pad_top + di * cell
            ch = ramp_char(count, vmax)
            op = 0.15 if count == 0 else min(1.0, 0.35 + 0.65 * (count / vmax))
            out += (f'<text x="{x}" y="{y+9}" font-size="{FONT_SIZE}" '
                    f'class="accent" opacity="{op:.2f}">{ch}</text>\n')

    out += SVG_FOOTER
    return out


# ---------------------------------------------------------------------------
def main():
    user, frm, to = fetch()
    calendar = user["contributionsCollection"]["contributionCalendar"]
    total = calendar["totalContributions"]
    days = flatten_days(calendar)
    weekly = weekly_totals(days, n_weeks=12)
    streak_data = compute_streaks(days)
    by_bytes, by_repo, _ = language_stats(user["repositories"])

    outputs = {
        "heading-activity.svg": build_heading_svg("activity"),
        "stats.svg": build_stats_svg(total, weekly, frm, to),
        "streak.svg": build_streak_svg(streak_data),
        "langs.svg": build_langs_svg(by_bytes, by_repo),
        "year.svg": build_year_svg(days),
    }

    repo_root = os.path.abspath(os.path.join(HERE, ".."))
    for filename, content in outputs.items():
        path = os.path.join(repo_root, filename)
        with open(path, "w") as fh:
            fh.write(content)
        print(f"wrote {path} ({len(content)} bytes)")


if __name__ == "__main__":
    sys.exit(main())
