# ZOOP Dark-Luxury Factory

A cloud-first dark-luxury short-video factory built for GitHub Actions. It keeps the validated visual baseline (25 seconds, 17 cuts, dark-luxury grading) and adds an experiment/learning loop so the content mix evolves from the performance of your own posts.

## What is automated

- Generates dark-luxury vertical edits from Pexels/Pixabay stock footage.
- Uses Gemini as an optional creative director and falls back safely if Gemini is unavailable.
- Keeps the approved dark grade and tracked minimalist text style.
- Avoids recently reused stock clips across videos.
- Generates a short caption variant for each post.
- Produces a provenance/rights manifest for every export.
- Generates and schedules up to four upload-ready posts per day via GitHub Actions.
- Records every generated experiment in `data/generated.csv`.
- Collects post performance at 24 hours, 72 hours and 7 days when Zoop exposes it.
- Keeps a manual metrics form as a fallback.
- Re-analyzes theme/copy/caption performance after each metrics entry and weekly.
- Uses a 70/30 exploit/explore strategy after enough samples, while forcing early exploration so every variant gets tested.

The publisher and metrics collector use the account's encrypted Playwright storage state from
`ZOOP_STORAGE_STATE_B64`. The session file is deleted from the runner after every workflow.

When ZOOP presents an AI Content / AI Edited Content label during upload, use the appropriate label for content that falls within ZOOP's current labelling rules.

## Baseline

The automatic factory uses:

- Style: `dark_luxury`
- Duration: `25s`
- Clips: `12`
- BPM: `100`
- Position: centered minimalist text

## Experiment factors

### Theme

- `dark_cars`: supercars, Dubai night, watches, dark business/lifestyle
- `money`: cash, watches, suits, cars, premium interiors
- `dark_life`: nightlife, restaurants, hotels, Dubai, private jets
- `mixed_dark`: broad dark-luxury mix

### Overlay copy

- `one_day` → `ONE DAY.`
- `soon` → `SOON.`
- `none` → no text

### Caption type

- `choice`: simple A/B question
- `aspiration`: short aspirational question
- `minimal`: minimal dark-luxury caption

## Workflows

### Generate ZOOP Luxury Video

Manual generator. You can choose the experiment factors yourself or leave them on `auto`.

### Automatic ZOOP Content Factory

Runs twice per day at 07:00 and 17:00 UTC. Each run creates one 25s / 17-cut dark-luxury video and uploads a GitHub artifact named `zoop-auto-<run_id>`.

The artifact contains:

- `ZOOP_READY.mp4`
- `caption.txt`
- `post_card.md`
- `EXPERIMENT_ID.txt`
- `creative_plan.json`
- `sources.json`
- `rights_manifest.json`

### Record ZOOP Metrics

After posting a video, run this workflow and enter its `experiment_id` plus the metrics ZOOP exposes to you:

- views/reach
- likes
- comments
- shares
- followers gained
- completion rate if available
- average watch seconds if available

The workflow updates `data/metrics.csv`, `data/strategy_state.json` and `reports/latest.md`.

### Collect ZOOP Metrics

The scheduled publisher stores the link between each `experiment_id` and its Zoop post in
`data/published_posts.csv`. The collector runs every six hours and captures one performance
snapshot after 24 hours, 72 hours and 7 days.

- `data/metric_snapshots.csv` keeps the three historical checkpoints.
- `data/metrics.csv` keeps only the newest checkpoint for each post, so one post never counts
  three times in the learning model.
- `output/zoop_metrics_raw.json` is uploaded as a short-lived diagnostic artifact and contains
  the Zoop API responses used by the parser.
- Likes/reactions and comments are still saved when views are unavailable, but a row is not sent
  to the learning model unless Zoop exposes a real view/reach count.

The manual `Record ZOOP Metrics` workflow remains available as a fallback.
On its first runs, the collector also backfills older generated posts when their caption has one
unique exact match on the Zoop profile; ambiguous repeated captions are deliberately ignored.

### Analyze ZOOP Strategy

Runs weekly and can also be run manually. It builds a report showing which themes, overlay texts and caption styles are winning.

## Internal scoring

The pipeline uses its own comparison score. This is not claimed to be ZOOP's ranking formula.

The score rewards:

- likes
- comments more heavily than likes
- shares more heavily than comments
- followers gained most heavily
- completion rate as an optional secondary signal

Results are smoothed so one tiny post cannot immediately become the permanent winner.

## Strategy logic

At first, the system prioritizes under-tested variants until each factor has enough observations. After that it uses approximately:

- 70% exploitation: choose the strongest factor values so far
- 30% exploration: keep testing alternatives

This avoids getting stuck on a false winner too early.

## Clip reuse protection

`data/used_stock.csv` stores recent stock IDs. New videos avoid the most recently used stock clips so the account does not repeatedly recycle the same footage.

## Provenance

Every package contains `rights_manifest.json`, including provider, stock ID, source page, author when available, search query and license reference. Keep this file with the corresponding post archive.

## Music

Add music you have the right to use in `assets/music/`. With `--music auto`, the generator randomly selects an audio file from that folder. If the folder contains no track, the exported video contains a silent audio stream.

## API secrets

Set these GitHub repository secrets:

- `PEXELS_API_KEY`
- `PIXABAY_API_KEY`
- `GEMINI_API_KEY` (optional but recommended)

## First recommended operating loop

1. Let the factory create and schedule up to four videos per day.
2. Let `Collect ZOOP Metrics` measure each post at 24 hours, 72 hours and 7 days.
3. Use `Record ZOOP Metrics` only when an automatic measurement is unavailable.
4. Repeat without manually changing the visual baseline.
5. Review `reports/latest.md` after roughly 20, 40 and 60 measured posts.

The goal is to optimize from your own account data rather than pretend to know ZOOP's private ranking formula.

## V4 known-audio strategy

The pipeline now has a dark-luxury audio catalog in `data/audio_catalog.json`. It can select among `TE CONOCÍ`, `GOZALO`, `NO ERA AMOR`, `LUZ ROJA`, `LUNA BALA`, `SEMPERO`, and `PASSO BEM SOLTO`, mapping each one to the visual theme and learning from recorded post metrics.

The catalog stores a preferred 25-second starting point seeded from current Shazam Popular Segments. The pipeline also records the chosen audio in `generated.csv` and `metrics.csv`, so `Analyze ZOOP Strategy` can compare audio performance along with theme, overlay, and caption.

Commercial audio files are intentionally not included or downloaded. If you are authorized to use a track, see `assets/music/README.md` for the expected filename. If the selected file is absent, the video still renders and `output/audio_plan.json` tells you which audio was selected and which segment to use.
