# Hindi short production workflow

A compact, portable workflow for producing one source-checked Hindi short: research → one script → meaningful shots → generated art → restrained motion → captions → local MP4.

This repository contains workflow instructions, generic templates and reusable code only. It contains no previous episodes, scripts, artwork, audio, videos, owner history or credentials. It does not run production by itself; an assistant supplies research, image generation and visual judgment.

## Give this to another assistant

Clone/download this repository, supply your topic and private context separately, and paste [START_PROMPT.md](START_PROMPT.md). Read [AGENTS.md](AGENTS.md) for the operating rules and [WORKFLOW.md](WORKFLOW.md) for the sequence. Do not upload private context to this public repository.

The assistant needs browsing, image generation, filesystem access and local Python execution. A ChatGPT environment without these capabilities cannot finish the full movie unattended. It should identify the missing capability and complete everything else it can, without inventing generated assets or checks.

## Local renderer

Python 3.10+ and an FFmpeg build with libass are required. The imageio-ffmpeg dependency normally provides FFmpeg. The renderer uses Pillow and NumPy. Install in a virtual environment:

```sh
python -m venv .venv
# Activate the environment using your shell's normal command.
python -m pip install -r requirements.txt
```

Use templates as schemas, not finished production inputs. Paths inside JSON are relative to the clone root. All production inputs and outputs belong under the ignored `runs/` directory. Populate the source/script/board/mask plan and create real PNGs, then:

```sh
python tools/prepare.py runs/my-short
python system/production/local-renderer.py runs/my-short/job.json --sheets
# Inspect every actual image and motion-zones.jpg; an independent reviewer
# writes runs/my-short/reviews/images-review.json using the template schema.
python system/production/local-renderer.py runs/my-short/job.json
python tools/review_page.py runs/my-short
```

The final render performs one video encode, full decode/count, encoded midpoint extraction and audio metering when audio is supplied. Human/agent inspection of actual outputs is still required. Correct only failed checks; avoid repeated unchanged renders.

Default output is 720×1280, 24fps, H.264 MP4 with Hindi captions. Install a Devanagari font appropriate to the host and set `subtitle_font` in job.json (default: Nirmala UI on Windows; Noto Sans Devanagari elsewhere). Check actual encoded Hindi shaping and line breaks.

The renderer supports optional cleared music and wind; omit either or both for a silent output. It does **not** synthesize narration or align a recorded voice. The default deliverable is a music/SFX-only review cut with estimated timings. If an actual voice recording is supplied, align the edit to it and adapt the audio mix before claiming a narrated master.

Style descriptions are in STYLE.md. Exact approved reference images must be supplied privately; they are intentionally absent here. Audio and its licence evidence must also be supplied privately or obtained from a verified permitted source. No paid API, upload, publication or external editor integration is required.

## Keep it small

Keep one run ledger, one bilingual source companion, one script, one shot plan, actual assets/prompts, short reviews and one master page. Generated captions, export metadata and technical samples are legitimate renderer outputs; do not duplicate them into role folders or multiple handoff packs. `--sheets` generates only preparation sheets/captions, not an intermediate movie.

`runs/`, `private-context/` and `references/` are ignored as a convenience, not a security boundary. Only explicitly stage workflow files. Never use `git add -f` to publish production assets.
