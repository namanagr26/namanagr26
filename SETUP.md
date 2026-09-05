# Setup

This repo generates the four graphics on your GitHub profile (contribution
total, streaks, top languages, contribution calendar) using nothing but the
GitHub API and a scheduled Action — no third-party stats widgets.

## 1. Create the repo

The repo name must match your GitHub username exactly.

```bash
gh repo create <your-username> --public --clone
cd <your-username>
```

Copy everything from this folder into it (README.md, .github/, scripts/),
then commit and push:

```bash
git add -A
git commit -m "init profile"
git push
```

## 2. Run it once manually

Go to the repo on GitHub → **Actions** tab → **refresh stats** → **Run
workflow**. This does the first generation of stats.svg, streak.svg,
langs.svg, and year.svg, and commits them straight into the repo.

You need to do nothing else — the workflow has `permissions: contents:
write` and uses the repo's own automatic `GITHUB_TOKEN`, so no secrets to
configure.

## 3. Check your profile

Visit `github.com/<your-username>`. If the README doesn't show up right
away, GitHub caches newly created profile READMEs — edit it once through
the web UI (even just adding a space and removing it) to force a refresh.

## 4. It updates itself

The Action re-runs daily at 05:17 UTC and only commits when something
actually changed, so you won't get a stream of empty commits.

## 5. Add the ASCII portrait (optional, one-time)

This is separate from the daily refresh — a photo doesn't change day to
day, so it's generated once, locally, and committed like a normal file.

```bash
pip install -r scripts/requirements-portrait.txt
python3 scripts/generate_portrait.py path/to/your/photo.jpg
```

Photo requirements, since the ASCII conversion draws with shadow, not
detail (about 13 brightness levels to work with):

- **Side light** — a window at roughly 45°, one side of the face lit, the
  other in shadow. Flat frontal light renders the face as a featureless hole.
- **Fill the frame** — crop tight, chin to just above the hair.
- **High resolution** — 1200px+ on the crop; thin features like glasses
  frames get averaged away below that.
- **Plain background**, and avoid dark clothing against a dark wall.
- **Slight angle**, not dead-on, for a shadow edge on the nose and jaw.

This writes `portrait.svg` into the repo root. Then uncomment the portrait
block at the top of `README.md`, commit both, and push.

The first run downloads a ~176 MB background-removal model (cached after
that). A 50-row portrait takes a few seconds to generate and about 4–5s to
finish "typing" when someone loads your profile.

## Notes

- The font embedded in the SVGs is JetBrains Mono (SIL OFL 1.1), subset to
  ~4.5 KB per weight — the license file is in `scripts/fonts/OFL.txt` and
  travels with the repo since it's public.
- Only your **public** repositories are counted for language stats
  (`privacy: PUBLIC` in the query), so the numbers are the same whether you
  or the Action's token generates them.
- `scripts/test_mock.py` regenerates the SVGs from fabricated data into a
  `preview/` folder, useful for tweaking colors/layout without hitting the
  real API or waiting on the Action.
