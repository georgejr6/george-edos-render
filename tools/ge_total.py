"""Total frame count of a George Edos tutorial composition (same math as buildTutorial in src/kit/tutorial.tsx).
Usage: python tools/ge_total.py ge01   -> prints the frame count"""
import json, math, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FPS, LEAD, GAP, TAIL = 30, 8, 1, 10


def build(ep):
    d = os.path.join(ROOT, "episodes", ep)
    script = json.load(open(os.path.join(d, "script.json"), encoding="utf-8"))
    timing = json.load(open(os.path.join(d, "timing.json"), encoding="utf-8"))
    cur, starts = 0, {}
    for i, s in enumerate(timing["scenes"]):
        local = LEAD
        for b in s["beats"]:
            local += math.floor(b["dur"] * FPS + 0.5) + GAP
        hold = math.floor((script["scenes"][i].get("hold") or 0) * FPS + 0.5)
        ln = local - GAP + TAIL + hold
        starts[s["id"]] = cur
        cur += ln
    return script, starts, cur + 6


if __name__ == "__main__":
    print(build(sys.argv[1])[2])
