"""Two-pass loudness master to YouTube's target (-14 LUFS integrated, -1 dBTP). Video stream is copied untouched.

Usage: python tools/master.py in.mp4 out.mp4
"""
import json, os, re, subprocess, sys

NO_WINDOW = 0x08000000 if os.name == "nt" else 0
TARGET = "I=-14:TP=-1.0:LRA=11"


def run(args):
    return subprocess.run(args, capture_output=True, text=True, creationflags=NO_WINDOW)


def main(src, dst):
    global TARGET
    ep = os.path.splitext(os.path.basename(dst))[0]
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if os.path.exists(os.path.join(root, "episodes", ep, "layout.json")):
        TARGET = "I=-15:TP=-1.2:LRA=11"  # NOVAM documentaries: owner spec -15 LUFS (audio already mastered by cf_mix.py)
    r = run(["ffmpeg", "-hide_banner", "-i", src, "-af", f"loudnorm={TARGET}:print_format=json", "-f", "null", "-"])
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.S)
    if not m:
        sys.exit("loudnorm analysis failed:\n" + r.stderr[-800:])
    a = json.loads(m.group(0))
    af = (f"loudnorm={TARGET}:measured_I={a['input_i']}:measured_TP={a['input_tp']}:measured_LRA={a['input_lra']}"
          f":measured_thresh={a['input_thresh']}:offset={a['target_offset']}:linear=true")
    r = run(["ffmpeg", "-hide_banner", "-y", "-i", src, "-c:v", "copy", "-af", af, "-ar", "48000", "-c:a", "aac", "-b:a", "256k", dst])
    if r.returncode:
        sys.exit(r.stderr[-800:])
    chk = run(["ffmpeg", "-hide_banner", "-i", dst, "-af", "ebur128=framelog=quiet", "-f", "null", "-"]).stderr
    i = re.findall(r"I:\s+(-?[\d.]+) LUFS", chk)
    print(f"in {a['input_i']} LUFS -> out {i[-1] if i else '?'} LUFS : {dst}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
