# ZOOP Luxury Factory

Cloud-run vertical luxury edit generator. It is designed to run in GitHub Actions, so the editing/rendering work happens on a GitHub-hosted runner rather than on your computer.

## What it creates

A 9:16 luxury-lifestyle edit assembled from licensed stock-video API results: yachts, Dubai, supercars, adult pool/beach lifestyle, private jets, villas, hotels, nightlife, watches and similar footage.

The final artifact contains:

- `ZOOP_READY.mp4`
- `caption.txt`
- `creative_plan.json`
- `sources.json`

There is no YouTube uploader and no ZOOP automation. The output is simply prepared for manual upload to ZOOP.

## Pipeline

1. GitHub Actions starts an Ubuntu runner.
2. Gemini optionally acts as creative director and chooses the sequence, minimal overlay text and caption.
3. Pexels and/or Pixabay are searched for matching stock clips.
4. The system prefers portrait/high-resolution clips and avoids reusing the same source in one edit.
5. Each source is cut to a short segment and cropped to 1080x1920.
6. Cuts are distributed around the BPM you specify.
7. The clips are concatenated with hard cuts.
8. Optional minimal text is burned into the image.
9. Optional music is added.
10. GitHub uploads the final package as a workflow artifact.

## Required secrets

In GitHub: `Settings -> Secrets and variables -> Actions`.

You need at least one stock provider:

- `PEXELS_API_KEY`
- `PIXABAY_API_KEY`

Optional:

- `GEMINI_API_KEY`

If Gemini is missing, the generator still works using built-in creative presets.

## Music

Put music you have the right to use inside `assets/music/` and commit it to your own repository, then type its filename when running the workflow.

Example: `luxury-house-01.mp3`

If no music is provided, the output is generated with silent audio. The repo deliberately does not scrape copyrighted TikTok/Instagram music.

## Run

Open `Actions -> Generate ZOOP Luxury Video -> Run workflow`.

Recommended first test:

- style: `mixed`
- duration: `15`
- clips: `10`
- BPM: `120`
- text mode: `minimal`
- music file: leave blank for the first technical test

After the job finishes, download the `zoop-luxury-video` artifact from the workflow run.

## Styles

- `dark_luxury`: night cars, Dubai, watches, jets, nightlife
- `summer_luxury`: pools, beaches, yachts, Monaco, villas
- `dubai`: Dubai-heavy edit
- `yacht_life`: yachts, pools, beaches, Monaco
- `mixed`: broad luxury mix

## How the montage works

For a 15-second video with 10 clips at 120 BPM, the renderer creates roughly 1-2 second cuts. It downloads longer stock videos and randomly chooses a short section from each source instead of always taking the opening seconds. Each section is resized/cropped to 1080x1920 at 30 fps and joined with hard cuts.

The BPM is used as a rhythmic guide. The system draws cut durations from 2, 3 or 4 beats and then rescales the sequence to land exactly on the requested final duration.

## Content sourcing

`sources.json` records provider, source ID and source page for every clip used. Review the current Pexels/Pixabay licenses and any applicable model/property restrictions for your intended use before publishing commercially.
