"""Build one portable review page without duplicating media or source text."""
from pathlib import Path
import html
import json
import sys
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]

def main():
    p = (ROOT / sys.argv[1]).resolve()
    p.relative_to(ROOT / "runs")
    read = lambda f: json.loads(f.read_text(encoding="utf-8-sig"))
    esc = lambda value: html.escape(str(value), quote=True)
    board = read(p / "storyboard.json")
    script_path = (ROOT / board["script_file"]).resolve()
    script_path.relative_to(ROOT)
    script = read(script_path)
    movie = quote(board.get("movie_name", "short.mp4"), safe="")
    lines = "".join(f'<p lang="hi">{esc(line["text"])}</p>' for line in script["lines"])
    cards = "".join(
        f'<article><h2>{esc(s["id"])} · {esc(s["title"])}</h2>'
        f'<img src="images/{quote(s["id"], safe="")}.png" alt="{esc(s["title"])}">'
        f'<p>{s["start_ms"]/1000:g}–{s["end_ms"]/1000:g}s EST</p>'
        f'<p>{esc(s.get("description", ""))}</p></article>' for s in board["shots"])
    page = f'''<!doctype html><html lang="hi"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(board["title"])}</title><style>
body{{font:18px/1.7 system-ui,sans-serif;background:#f4efe5;color:#243638;margin:0}}
main{{max-width:950px;margin:auto;padding:24px}}video{{display:block;max-width:100%;max-height:78vh;margin:auto}}
article{{border-top:1px solid #c6bda9;padding:24px 0}}img{{max-width:100%;width:280px}}a{{color:#075b68}}
</style><main><h1>{esc(board["title"])}</h1>
<p>{board["duration_ms"]/1000:g}s EST · {len(board["shots"])} scenes · review cut.
No recorded voice, final owner approval or unperformed listening is implied.</p>
<video controls playsinline src="motion/{movie}"></video>
<p><a href="sources.md">Sources and context</a> · <a href="motion/subtitles-hi.srt">Hindi subtitles</a>
 · <a href="run.json">Run and performed checks</a></p><h2>Working Hindi script</h2>{lines}{cards}</main></html>'''
    (p / "index.html").write_text(page, encoding="utf-8")
    print(p / "index.html")

if __name__ == "__main__":
    main()
