"""Prepare generic local render inputs; never writes review verdicts."""
from pathlib import Path
import hashlib
import json
import os
import sys

ROOT = Path(__file__).resolve().parents[1]

def project(value):
    p = (ROOT / value).resolve()
    p.relative_to(ROOT)
    return p

def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))

def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def main():
    p = project(sys.argv[1])
    p.relative_to(ROOT / "runs")
    rel = lambda value: value.relative_to(ROOT).as_posix()
    board = read(p / "storyboard.json")
    plan = read(p / "mask-plan.json")
    assert board["shots"], "No shots"
    assert board["duration_ms"] >= 5000, "Short must allow caption/audio fades"
    assert len({s["id"] for s in board["shots"]}) == len(board["shots"]), "Duplicate shot IDs"
    cursor = 0
    images, masks = {}, {}
    for shot in board["shots"]:
        sid = shot["id"]
        assert shot["start_ms"] == cursor and shot["end_ms"] > cursor, "Shots must be contiguous"
        cursor = shot["end_ms"]
        image = p / "images" / f"{sid}.png"
        cfg = plan["shots"][sid]
        for box in cfg["protected_boxes"] + cfg["effect_zones"]:
            assert len(box) == 4 and all(0 <= v <= 1 for v in box), "Invalid normalized rectangle"
            assert box[0] < box[2] and box[1] < box[3], "Empty rectangle"
        images[sid] = rel(image)
        masks[sid] = dict(cfg, image_hash=hashlib.sha256(image.read_bytes()).hexdigest())
    assert cursor == board["duration_ms"], "Shot duration mismatch"
    script = read(project(board["script_file"]))
    line_ids = [line["id"] for line in script["lines"]]
    mapped = [lid for shot in board["shots"] for lid in shot["narration_line_ids"]]
    assert line_ids == mapped, "Each script line must appear once in sequence"
    (p / "motion").mkdir(exist_ok=True)
    (p / "reviews").mkdir(exist_ok=True)
    write(p / "motion/masks.json", {"method": "Manually inspected normalized rectangles", "shots": masks})
    audio = plan.get("audio", {})
    for key in ("music", "wind"):
        if audio.get(key):
            assert project(audio[key]).is_file(), f"Missing {key}"
    if any(audio.get(key) for key in ("music", "wind")):
        assert (p / "audio-rights.md").is_file(), "Record actual audio source/licence evidence in audio-rights.md"
    write(p / "job.json", dict(
        output_dir=rel(p / "motion"), board_file=rel(p / "storyboard.json"),
        script_file=board["script_file"], masks_file=rel(p / "motion/masks.json"),
        image_review=rel(p / "reviews/images-review.json"), images=images,
        movie_name=board.get("movie_name", "short.mp4"), audio=audio,
        subtitle_font=plan.get("subtitle_font", "Nirmala UI" if os.name == "nt" else "Noto Sans Devanagari"),
        camera_overrides=plan.get("camera_overrides", {})))
    print(f"Prepared {len(images)} real image inputs. No reviews or approvals were created.")

if __name__ == "__main__":
    main()
