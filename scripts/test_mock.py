"""Local test harness -- generates the SVGs from fabricated data so the
rendering logic can be checked without a live GitHub token."""
import datetime as dt
import os
import random

os.environ.setdefault("GITHUB_TOKEN", "dummy")
os.environ.setdefault("GH_LOGIN", "namanagr26")

import generate_stats as gs  # noqa: E402

random.seed(7)

today = dt.date.today()
days = []
for i in range(365, -1, -1):
    d = today - dt.timedelta(days=i)
    # fabricate a plausible contribution pattern with a couple of streaks and gaps
    if random.random() < 0.18:
        count = 0
    else:
        count = random.choice([1, 1, 2, 2, 3, 4, 6, 9])
    days.append((d.isoformat(), count))

# force a clean current streak at the tail
for i in range(1, 6):
    days[-i] = (days[-i][0], random.choice([2, 3, 5]))

total = sum(c for _, c in days)
weekly = gs.weekly_totals(days, n_weeks=12)
streak_data = gs.compute_streaks(days)

by_bytes = {"Python": 540000, "Jupyter Notebook": 210000, "HTML": 150000,
            "CSS": 60000, "JavaScript": 40000}
by_repo = {"HTML": 3, "Python": 2, "Jupyter Notebook": 2, "CSS": 1}

frm = dt.datetime.combine(today - dt.timedelta(days=364), dt.time(0, 0, 0),
                           tzinfo=dt.timezone.utc)
to = dt.datetime.combine(today, dt.time(23, 59, 59), tzinfo=dt.timezone.utc)

out_dir = os.path.join(os.path.dirname(__file__), "..", "preview")
os.makedirs(out_dir, exist_ok=True)

files = {
    "heading-activity.svg": gs.build_heading_svg("activity"),
    "stats.svg": gs.build_stats_svg(total, weekly, frm, to),
    "streak.svg": gs.build_streak_svg(streak_data),
    "langs.svg": gs.build_langs_svg(by_bytes, by_repo),
    "year.svg": gs.build_year_svg(days),
}

for name, content in files.items():
    path = os.path.join(out_dir, name)
    with open(path, "w") as fh:
        fh.write(content)
    print(f"wrote {path} ({len(content)} bytes)")

print("total:", total)
print("streaks:", streak_data)
