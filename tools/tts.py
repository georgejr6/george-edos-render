"""Generate narration per beat with OpenAI TTS, align words with local faster-whisper, write timing.json.

Usage: python tools/tts.py episodes/cf01 [--engine clone|eleven|auto]
- clone (default): local F5-TTS founder clone. eleven: ElevenLabs (paid key file required, see ELEVEN_KEY_FILE).
  auto: eleven when the paid key file exists, else clone. Every engine writes the same timing.json / beat files.
- Beats whose text/voice are unchanged are reused from cache (hash in filename).
- Word timings (seconds from beat start) are cached next to each mp3 as .words.json.
The voice is a placeholder until the owner's voice clone exists; swap the provider in synth() only.
"""
import hashlib, json, os, re, shutil, subprocess, sys, time, urllib.error, urllib.request

NO_WINDOW = 0x08000000 if os.name == "nt" else 0
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_model = None


def api_key():
    if os.environ.get("OPENAI_API_KEY", "").startswith("sk-"):
        return os.environ["OPENAI_API_KEY"]
    folder = os.environ.get("CODING_KEYS_DIR", r"C:\Users\13478\Desktop\coding")
    for name in ("myconsent.me OPENAI secret key.txt", "family financial planner, apikeys claude + openai.txt"):
        p = os.path.join(folder, name)
        if os.path.exists(p):
            text = open(p, encoding="utf-8", errors="ignore").read()
            # never pick an Anthropic key (sk-ant-...)
            for m in re.finditer(r"sk-(?!ant-)[A-Za-z0-9_\-]{20,}", text):
                return m.group(0)
    sys.exit("no OpenAI key found")


def duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True, creationflags=NO_WINDOW)
    if r.returncode != 0 or not r.stdout.strip():
        raise RuntimeError(f"ffprobe failed on {path}: {r.stderr.strip()}")
    return float(r.stdout.strip())


def synth(key, v, text, path):
    body = json.dumps({"model": v["model"], "voice": v["voice"], "input": text,
                       "instructions": v["instructions"], "response_format": "mp3"}).encode()
    req = urllib.request.Request("https://api.openai.com/v1/audio/speech", data=body,
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    data = b""
    for attempt in range(4):  # 3 retries with backoff on rate limits, 5xx and network trouble
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read()
            break
        except urllib.error.HTTPError as e:
            if e.code != 429 and e.code < 500 or attempt == 3:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
            if attempt == 3:
                raise
        time.sleep((2, 6, 15)[attempt])
    if len(data) < 1024:
        raise RuntimeError(f"TTS returned only {len(data)} bytes for: {text[:60]}")
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)  # atomic: a failed download never leaves a cached partial file


CLONE_PY = r"C:\Users\13478\dev\voiceclone-venv\Scripts\python.exe"
DEFAULT_CLONE = {
    "provider": "clone",
    # two solo reference clips of the owner (lecture + webinar); clone_tts keeps the best take per line
    "refs": [
        {"audio": r"C:\Users\13478\dev\novam-yt\voice\dataset\clips\nomad_skill_00017279.wav",
         "text": "Throughout your membership, you will get access to courses in each of these topics produced by real professionals and professors who have strong expertise in the field."},
        {"audio": r"C:\Users\13478\dev\novam-yt\voice\dataset\clips\creator_00009880.wav",
         "text": "Now what you will be learning during this webinar is what is a creator economy? Artists are businesses."},
    ],
    "wps": 2.75,
}


# ElevenLabs: paid key only (free tier is not licensed for commercial use). Owner drops the key in this file.
ELEVEN_KEY_FILE = os.environ.get("ELEVENLABS_KEY_FILE", r"C:\Users\13478\Desktop\coding\elevenlabs paid key.txt")
DEFAULT_ELEVEN = {
    "provider": "eleven",
    "model": "eleven_multilingual_v2",
    # owner 2026-11-09 (late): "Mwosa 2026 Narrator", built from his webinar/course narration (Judge sim 0.958).
    # The stream clone nOTXz1aDdQiUIbsoWwsk was REJECTED as too casual: never use it.
    # FINAL (owner-approved 2026-11-09): "Mwosa 2026 Studio Narrator", studio-remixed clone (no pops, no earbud tone).
    # Superseded/rejected: nOTXz1aDdQiUIbsoWwsk (stream), 9bCzF52TkShZa1jCCzUM (narrator), HGZBAisKwRcEJ8oEx31R (studio).
    "voice_id": "yNyuTGcqoxsMSZ8aSAz7",
    "format": "mp3_44100_192",
    "pace": 1.0,  # owner: natural pace already too fast; slow via settings.speed, no atempo
    "settings": {"stability": 0.65, "similarity_boost": 0.8, "style": 0.05, "use_speaker_boost": True, "speed": 0.9},
    "master": "light1",
}
# owner's narration mastering chain, applied to every ElevenLabs line before timing/render
# FINAL owner recipe: one sentence per call; per-sentence trim + micro fades + breath pad (0.45 s, or 0.8 s before a
# big question/turn: beats ending in "?" or scenes with "pause": "long"); then a LIGHT master, a tad deeper.
def sent_af(pad):
    return ("silenceremove=start_periods=1:start_threshold=-50dB,areverse,silenceremove=start_periods=1:start_threshold=-50dB,areverse,"
            f"afade=t=in:d=0.012,areverse,afade=t=in:d=0.05,areverse,apad=pad_dur={pad}")


# owner 2026-11-09 late: previous chain sounded "too filtered" -> light touch, no pitch shift, no de-nasal cuts
MASTER_AF = "highpass=f=60,lowshelf=f=130:g=1,equalizer=f=1000:t=q:w=1.4:g=-1,acompressor=threshold=-22dB:ratio=1.8:attack=15:release=150:makeup=1.5,loudnorm=I=-16:TP=-1.5:LRA=7"
GOOD_SIM, GOOD_WER = 0.80, 0.15  # a take below either bar gets ONE retake (max 2 takes per line: credit budget)


def judge(items, work_dir):
    """items = [(mp3, text)] -> {mp3: {sim, wer, score}} via the clone Judge in the voiceclone venv."""
    if not items:
        return {}
    if not os.path.exists(CLONE_PY):  # cloud brain / render droplet: no local Judge venv -> accept the take (no retake spend)
        return {f: {"file": f, "sim": 1.0, "wer": 0.0, "score": 1.0, "judged": False} for f, _ in items}
    jf = os.path.join(work_dir, "_judge_jobs.json")
    json.dump([{"file": f, "text": t} for f, t in items], open(jf, "w", encoding="utf-8"))
    r = subprocess.run([CLONE_PY, os.path.join(ROOT, "tools", "judge_takes.py"), jf], creationflags=NO_WINDOW)
    if r.returncode:
        raise RuntimeError("judge failed")
    return {x["file"]: x for x in json.load(open(jf[:-5] + ".scores.json", encoding="utf-8"))}


def eleven_key():
    if os.environ.get("ELEVEN_PAID_KEY"):
        return os.environ["ELEVEN_PAID_KEY"].strip()
    if not os.path.exists(ELEVEN_KEY_FILE):
        return None
    text = open(ELEVEN_KEY_FILE, encoding="utf-8", errors="ignore").read()
    m = re.search(r"sk_[A-Za-z0-9]{20,}", text) or re.search(r"\b[A-Za-z0-9]{32,}\b", text)
    return m.group(0) if m else None


def eleven_fetch(key, v, text, src, prev_text=None, next_text=None):
    """One ElevenLabs call -> raw take saved at src (kept, so re-mastering never re-spends credits)."""
    body = {"text": text, "model_id": v["model"], "voice_settings": v["settings"]}
    if prev_text:
        body["previous_text"] = prev_text[-400:]  # keeps delivery continuous across sentence calls
    if next_text:
        body["next_text"] = next_text[:400]
    req = urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{v['voice_id']}?output_format={v.get('format', 'mp3_44100_128')}",
                                 data=json.dumps(body).encode(), headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    if len(data) < 1024:
        raise RuntimeError(f"ElevenLabs returned only {len(data)} bytes for: {text[:60]}")
    with open(src + ".part", "wb") as f:
        f.write(data)
    os.replace(src + ".part", src)


def eleven_master(src, path, pad):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", src, "-af", sent_af(pad) + "," + MASTER_AF,
                        "-ar", "44100", "-c:a", "libmp3lame", "-b:a", "192k", "-metadata", "comment=AI-generated voice (ElevenLabs)", path + ".tmp.mp3"],
                       capture_output=True, text=True, creationflags=NO_WINDOW)
    if r.returncode:
        raise RuntimeError(r.stderr)
    os.replace(path + ".tmp.mp3", path)


def gen_key(v, text):
    return "el" + hashlib.sha1((v["model"] + v["voice_id"] + json.dumps(v["settings"], sort_keys=True) + text).encode()).hexdigest()[:8]


# OpenAI "standard" tier (customer Shorts): same trim / breath pad / loudness as the ElevenLabs chain, minus the EQ+compressor.
OAI_MASTER_AF = "highpass=f=60,loudnorm=I=-16:TP=-1.5:LRA=7"
OAI_PAD = 0.35


def openai_master(src, path, pad=OAI_PAD):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", src, "-af", sent_af(pad) + "," + OAI_MASTER_AF,
                        "-ar", "44100", "-c:a", "libmp3lame", "-b:a", "128k", "-metadata", "comment=AI-generated voice (OpenAI)", path + ".tmp.mp3"],
                       capture_output=True, text=True, creationflags=NO_WINDOW)
    if r.returncode:
        raise RuntimeError(r.stderr)
    os.replace(path + ".tmp.mp3", path)


def master_tag(pad):
    return "m" + hashlib.sha1((MASTER_AF + str(pad)).encode()).hexdigest()[:5]


def beat_key(v, text):
    if v.get("provider") == "eleven":
        return gen_key(v, text)
    if v.get("provider") == "mwosa":
        return "mw" + hashlib.sha1(("mwosa" + str((v.get("clone") or {}).get("version")) + str((v.get("clone") or {}).get("engine")) + MASTER_AF + text).encode()).hexdigest()[:8]
    if v.get("provider") == "kokoro":
        return "ko" + hashlib.sha1(("kokoro" + str(v.get("voice")) + str(v.get("speed")) + KOKORO_AF + text).encode()).hexdigest()[:8]
    if v.get("provider") == "silent":
        return "si" + hashlib.sha1(("silent" + str(SILENT_WPS) + text).encode()).hexdigest()[:8]
    if v.get("provider") == "owner":
        return "own"
    if v.get("provider") == "clone":
        return hashlib.sha1(("clone" + json.dumps(v.get("refs"), sort_keys=True) + str(v.get("wps")) + text).encode()).hexdigest()[:10]
    return hashlib.sha1((v.get("model", "") + v["voice"] + v["instructions"] + OAI_MASTER_AF + text).encode()).hexdigest()[:10]


def clone_batch(v, pending):
    """pending = [(text, mp3_path)]; one local F5-TTS run for all of them (model loads once)."""
    if not pending:
        return
    jobs = {"refs": v["refs"], "wps": v.get("wps", 2.75), "judge": True,
            "nfe": v.get("nfe", 32), "jobs": [{"text": t, "out": p[:-4] + ".wav"} for t, p in pending]}
    jf = os.path.join(os.path.dirname(pending[0][1]), "_clone_jobs.json")
    json.dump(jobs, open(jf, "w", encoding="utf-8"))
    r = subprocess.run([CLONE_PY, os.path.join(ROOT, "tools", "clone_tts.py"), jf], creationflags=NO_WINDOW)
    if r.returncode:
        raise RuntimeError("clone_tts failed")
    for _, p in pending:
        w = p[:-4] + ".wav"
        r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", w, "-c:a", "libmp3lame", "-q:a", "2",
                            "-metadata", "comment=AI-generated voice (Novam local clone)", p + ".tmp.mp3"],
                           capture_output=True, text=True, creationflags=NO_WINDOW)
        if r.returncode:
            raise RuntimeError(r.stderr)
        os.replace(p + ".tmp.mp3", p)
        os.remove(w)


# ------------------------------------------------------------------ $0 voice tiers (owner 2026-11-13: ElevenLabs only for priority lanes)
# kokoro: Kokoro-82M (Apache-2.0) via kokoro-onnx on our own CPU (render droplet / ops-runner). Model files live in KOKORO_DIR.
# silent: captions-only Shorts (no narration): silent beat files timed at reading speed; the renderer shows big kinetic text.
# owner:  the owner's own recorded take (episodes/<id>/owner_take.*): denoised, aligned to the beats with faster-whisper, cut per beat.
KOKORO_DIR = os.environ.get("KOKORO_DIR", "/opt/kokoro")
DEFAULT_KOKORO = {"provider": "kokoro", "voice": "am_michael", "speed": 1.08, "pace": 1.0}
# warm male narrator: kill sub-60 Hz rumble, a little chest, soften 3-4 kHz synthetic edge, gentle air, same loudness as ElevenLabs
KOKORO_AF = ("highpass=f=70,lowshelf=f=150:g=2,equalizer=f=3500:t=q:w=1.2:g=-2,highshelf=f=9000:g=1,"
             "acompressor=threshold=-22dB:ratio=2:attack=12:release=140:makeup=1.5,loudnorm=I=-16:TP=-1.5:LRA=7")
_kokoro = None


def kokoro_style(k, voice):
    """'am_michael' or a blend 'am_michael:0.7+am_fenrir:0.3' -> style vector (or the name, which kokoro-onnx accepts)."""
    if "+" not in voice and ":" not in voice:
        return voice
    parts = [(p.split(":")[0], float(p.split(":")[1]) if ":" in p else 1.0) for p in voice.split("+")]
    tot = sum(w for _, w in parts)
    vec = None
    for name, w in parts:
        s = k.get_voice_style(name) * (w / tot)
        vec = s if vec is None else vec + s
    return vec


def kokoro_batch(v, pending, pad_of):
    """pending = [(text, mp3_path, scene_id)] -> one model load, one wav per sentence, mastered to mp3 (same trim/breath as ElevenLabs)."""
    if not pending:
        return
    global _kokoro
    if _kokoro is None:
        try:
            from kokoro_onnx import Kokoro
        except ImportError:  # ops-runner: kokoro lives in its own venv next to the model files
            import glob
            sys.path += glob.glob(os.path.join(KOKORO_DIR, "venv", "lib", "python3*", "site-packages"))
            from kokoro_onnx import Kokoro
        _kokoro = Kokoro(os.path.join(KOKORO_DIR, "kokoro-v1.0.onnx"), os.path.join(KOKORO_DIR, "voices-v1.0.bin"))
    import soundfile as sf  # after the venv path fallback above
    style = kokoro_style(_kokoro, v.get("voice", DEFAULT_KOKORO["voice"]))
    for text, p, sid in pending:
        samples, sr = _kokoro.create(text, voice=style, speed=float(v.get("speed", 1.0)), lang="en-us")
        w = p[:-4] + ".src.wav"
        sf.write(w, samples, sr)
        r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", w, "-af", sent_af(pad_of(sid, text)) + "," + KOKORO_AF,
                            "-ar", "44100", "-c:a", "libmp3lame", "-b:a", "192k", "-metadata", "comment=AI-generated voice (Kokoro)", p + ".tmp.mp3"],
                           capture_output=True, text=True, creationflags=NO_WINDOW)
        if r.returncode:
            raise RuntimeError(r.stderr)
        os.replace(p + ".tmp.mp3", p)
        os.remove(w)
        print("kokoro", os.path.basename(p), flush=True)


class CloneGateFailed(RuntimeError):
    """A line of the owner clone failed the quality gate (WER/similarity): the caller voices the whole video with the fallback."""


def mwosa_batch(v, pending, pad_of):
    """Owner clone via brain/mwosa_infer.py (engine from the R2 pointer: fine-tuned Chatterbox, or GPT-SoVITS v2Pro) in the interpreter
    mwosa_setup.sh prepared: best-of-6 per line behind the hard gate (Whisper large-v3 WER <= 3% coherence, ECAPA >= 0.70: the owner's
    real clips only score 0.77-0.80), then the same trim/breath + light master as ElevenLabs."""
    if not pending:
        return
    gpu = os.path.join(os.path.dirname(pending[0][1]), "_gpu")  # wavs voiced on a RunPod GPU by the brain (brain/gpu_voice.py), already gated
    gw = lambda t: os.path.join(gpu, hashlib.sha1(t.encode("utf-8")).hexdigest()[:16] + ".wav")
    if os.path.exists(os.path.join(gpu, "_report.json")) and all(os.path.exists(gw(t)) for t, _, _ in pending):
        for t, p, _ in pending:
            shutil.copyfile(gw(t), p[:-4] + ".clone.wav")
        _mwosa_master(pending, pad_of)
        return
    c = v["clone"]
    ext = {"gpt": ".ckpt", "sovits": ".pth", "t3": ".safetensors", "ref_wav": ".wav", "ref_emb": ".npy"}
    w = {k: f"/root/mw/w/{c['version']}_{k}{ext[k]}" for k in c["urls"]}
    out_dir = os.path.dirname(pending[0][1])
    jf = os.path.join(out_dir, "_mwosa_job.json")
    try:  # shard processes: ~8 GB RAM each (GPT-SoVITS + Whisper large-v3 + ECAPA); decoding scales poorly over many threads
        mem_gb = int(next(l for l in open("/proc/meminfo") if l.startswith("MemTotal")).split()[1]) / 1048576
    except Exception:  # noqa: BLE001
        mem_gb = 8
    workers = max(1, min(4, int((mem_gb - 4) // 8), (os.cpu_count() or 2) // 2))
    json.dump({"engine": c.get("engine", "sovits"), "workers": workers, "params": c.get("params") or {}, "weights": w, "ref_text": c["ref_text"], "n": 6,
               "wer_max": 0.03, "sim_min": 0.70, "sim_short_min": 0.45, "report": os.path.join(out_dir, "_mwosa_report.json"),
               "lines": [{"text": t, "out": p[:-4] + ".clone.wav"} for t, p, _ in pending]}, open(jf, "w", encoding="utf-8"))
    py = os.environ.get("MWOSA_PY") or (open("/root/mw/python").read().strip() if os.path.exists("/root/mw/python") else "/root/gsv/venv/bin/python")
    r = subprocess.run([py, os.environ.get("MWOSA_INFER", "/root/brain/mwosa_infer.py"), jf], creationflags=NO_WINDOW)
    if r.returncode:
        raise CloneGateFailed(f"owner clone failed the quality gate or could not run (rc {r.returncode}); see _mwosa_report.json")
    _mwosa_master(pending, pad_of)


def _mwosa_master(pending, pad_of):
    for text, p, sid in pending:
        wv = p[:-4] + ".clone.wav"
        r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", wv, "-af", sent_af(pad_of(sid, text)) + "," + MASTER_AF,
                            "-ar", "44100", "-c:a", "libmp3lame", "-b:a", "192k", "-metadata", "comment=AI-generated voice (owner clone)", p + ".tmp.mp3"],
                           capture_output=True, text=True, creationflags=NO_WINDOW)
        if r.returncode:
            raise RuntimeError(r.stderr)
        os.replace(p + ".tmp.mp3", p)
        print("mwosa", os.path.basename(p), flush=True)


SILENT_WPS = 3.1  # on-screen reading speed (words/s): a 140-word Short stays under the 60 s Shorts cap


def silent_beat(text, p):
    """Captions-only beat: a silent file as long as it takes to read the line, plus evenly spaced word timings."""
    ws = text.split()
    dur = round(max(1.5, len(ws) / SILENT_WPS + 0.25), 2)
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", str(dur),
                        "-c:a", "libmp3lame", "-b:a", "64k", p + ".tmp.mp3"], capture_output=True, text=True, creationflags=NO_WINDOW)
    if r.returncode:
        raise RuntimeError(r.stderr)
    os.replace(p + ".tmp.mp3", p)
    step = (dur - 0.25) / max(1, len(ws))
    json.dump([{"w": w, "t": round(i * step, 3), "e": round((i + 1) * step, 3)} for i, w in enumerate(ws)],
              open(p[:-4] + ".words.json", "w", encoding="utf-8"))


OWNER_AF = "highpass=f=80,afftdn=nr=12:nf=-40,lowshelf=f=140:g=1,acompressor=threshold=-22dB:ratio=2:attack=12:release=150:makeup=1.5,loudnorm=I=-16:TP=-1.5:LRA=7"


def _norm_word(w):
    return re.sub(r"[^a-z0-9]", "", w.lower())


def owner_cut(ep_dir, script, out_dir):
    """The owner's recorded take -> one mastered file per beat. Whisper word times on the denoised take; each beat claims the next
    run of transcript words that best matches its own words (a flubbed line is skipped past; at least half its words must match)."""
    take = next((os.path.join(ep_dir, f) for f in sorted(os.listdir(ep_dir)) if f.startswith("owner_take.")), None)
    if not take:
        raise RuntimeError("voice provider 'owner' needs episodes/<id>/owner_take.(m4a|mp3|wav)")
    clean = os.path.join(out_dir, "owner_clean.wav")
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", take, "-ac", "1", "-ar", "44100", "-af", OWNER_AF, clean],
                       capture_output=True, text=True, creationflags=NO_WINDOW)
    if r.returncode:
        raise RuntimeError(r.stderr)
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        _model = WhisperModel("base.en", device="cpu", compute_type="int8")
    segs, _ = _model.transcribe(clean, language="en", word_timestamps=True, beam_size=1)
    tw = [(_norm_word(w.word), w.start, w.end) for s in segs for w in (s.words or []) if _norm_word(w.word)]
    pos, files = 0, {}
    for sc in script["scenes"]:
        for i, text in enumerate(sc["beats"]):
            want = [_norm_word(w) for w in text.split() if _norm_word(w)]
            best = None
            # nearest start (within ~2 min of speech) that matches the most words; a perfect match ends the search
            for st in range(pos, min(len(tw), pos + 300)):
                hit = sum(1 for a, b in zip(want, (x[0] for x in tw[st:st + len(want)])) if a == b)
                if best is None or hit > best[0]:
                    best = (hit, st)
                if hit == len(want):
                    break
            if not best or best[0] < 0.5 * len(want):
                raise RuntimeError(f"owner take: could not find line {sc['id']} b{i + 1} in the recording: {text[:60]}")
            st = best[1]; en = min(len(tw) - 1, st + len(want) - 1)
            a, b = max(0.0, tw[st][1] - 0.06), tw[en][2] + 0.12
            p = os.path.join(out_dir, f"{sc['id']}_b{i + 1}_own{hashlib.sha1((take + text).encode()).hexdigest()[:6]}.mp3")
            r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-i", clean,
                                "-af", "afade=t=in:d=0.02,areverse,afade=t=in:d=0.06,areverse,apad=pad_dur=0.4", "-c:a", "libmp3lame", "-b:a", "192k", p],
                               capture_output=True, text=True, creationflags=NO_WINDOW)
            if r.returncode:
                raise RuntimeError(r.stderr)
            files[(sc["id"], i)] = os.path.basename(p)
            pos = en + 1
    return files


def words(path):
    cache = path[:-4] + ".words.json"
    if os.path.exists(cache):
        return json.load(open(cache, encoding="utf-8"))
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        _model = WhisperModel("base.en", device="cpu", compute_type="int8")
    segs, _ = _model.transcribe(path, language="en", word_timestamps=True, beam_size=1)
    out = [{"w": w.word.strip(), "t": round(w.start, 3), "e": round(w.end, 3)} for s in segs for w in (s.words or [])]
    with open(cache, "w", encoding="utf-8") as f:
        json.dump(out, f)
    return out


# owner 2026-11-05: minimal "brought to you by Novam" spot before and after every long-form, matched service line
SPONSOR = {
    "automate": ("Automate your business.", "an automation"),
    "website": ("Build a website for your business.", "a website like this"),
    "app": ("Build a mobile app for your business.", "an app like this"),
    "novam_app": ("Run your business from one app.", "the NOVAM app"),
}


# owner 2026-11-09: aggressive booking CTA on news Shorts (script "cta": "book"); renderer shows the BookCard
BOOK_CTA = "Want AI working for your business? Book a free call at novam dot U.S."


def with_sponsor(script):
    svc = script.get("service")
    if script.get("format") == "short" and isinstance(script.get("cta"), dict):
        # custom spoken close (e.g. jobs.novam.us, staffing.novam.us); renderer shows the matching CtaCard
        if any(s["id"] == "sp_close" for s in script["scenes"]):
            return script
        s = dict(script)
        s["scenes"] = script["scenes"] + [{"id": "sp_close", "beats": [script["cta"]["say"]]}]
        return s
    if script.get("format") == "short" and script.get("cta") == "book":
        if any(s["id"] == "sp_close" for s in script["scenes"]):
            return script
        s = dict(script)
        s["scenes"] = script["scenes"] + [{"id": "sp_close", "beats": [BOOK_CTA]}]
        return s
    if not svc or any(s["id"] == "sp_open" for s in script["scenes"]):
        return script
    line, thing = SPONSOR.get(svc, SPONSOR["automate"])
    s = dict(script)
    if script.get("format") == "short":
        # Shorts: no pre-roll (retention lives in second one); minimal end card only
        s["scenes"] = script["scenes"] + [{"id": "sp_close", "beats": [f"Brought to you by Novam. {line}"]}]
        return s
    close = script.get("sponsor_close_say") or f"If you want {thing} built for your business, there's a free launch plan linked in the description."
    s["scenes"] = ([{"id": "sp_open", "beats": ["This video is brought to you by Novam.", line]}] + script["scenes"] +
                   [{"id": "sp_close", "beats": ["This video was brought to you by Novam.", close]}])
    return s


def main(ep_dir, engine="clone"):
    ep_dir = os.path.join(ROOT, ep_dir)
    script = with_sponsor(json.load(open(os.path.join(ep_dir, "script.json"), encoding="utf-8")))
    out_dir = os.path.join(ROOT, "public", script["id"], "vo")
    os.makedirs(out_dir, exist_ok=True)
    v = script.get("voice") or {}
    ekey = None
    explicit = bool(v.get("provider") or v.get("voice"))  # auto never overrides a script that pins its own voice
    if engine == "eleven" or (engine == "auto" and not explicit):
        ekey = eleven_key()
        if not ekey and engine == "eleven":
            sys.exit(f"--engine eleven needs the paid key file: {ELEVEN_KEY_FILE}")
    if ekey:
        user = v.get("eleven") or {}
        v = dict(DEFAULT_ELEVEN, **user)
        v["settings"] = dict(DEFAULT_ELEVEN["settings"], **(user.get("settings") or {}))
    elif not v.get("provider") and not v.get("voice"):
        v = dict(DEFAULT_CLONE, **v)  # new episodes default to the owner's local voice clone
        if script.get("format") == "short":
            v["wps"] = 3.05  # Shorts run a touch quicker
    if engine == "mwosa" or (engine in ("auto", "eleven") and v.get("provider") == "mwosa"):
        v = dict(v, provider="mwosa", pace=float(v.get("pace", 1.1)))  # owner pace ~1.1 (pitch-preserving atempo below)
    elif engine in ("kokoro", "silent", "owner") or (engine in ("auto", "eleven") and v.get("provider") in ("kokoro", "silent", "owner")):
        prov = engine if engine in ("kokoro", "silent", "owner") else v["provider"]
        v = dict(DEFAULT_KOKORO, **{k: x for k, x in v.items() if k != "provider"}) if prov == "kokoro" else {"provider": prov, "pace": 1.0}
        v["provider"] = prov
        v["pace"] = 1.0  # kokoro paces natively (speed), so no atempo on top; silent/owner are never sped up
    key = None
    timing = {"id": script["id"], "engine": v.get("provider", "openai"), "scenes": []}
    ownfiles = owner_cut(ep_dir, script, out_dir) if v.get("provider") == "owner" else {}
    if v.get("provider") == "kokoro":
        longp = {sc["id"] for sc in script["scenes"] if sc.get("pause") == "long"}
        kpad = lambda sid, t: 0.8 if (sid in longp or t.rstrip().endswith("?")) else 0.45
        pend = []
        for sc in script["scenes"]:
            for i, text in enumerate(sc["beats"]):
                p = os.path.join(out_dir, f"{sc['id']}_b{i + 1}_{beat_key(v, text)}.mp3")
                if not os.path.exists(p) or os.path.getsize(p) < 1024:
                    pend.append((text, p, sc["id"]))
        kokoro_batch(v, pend, kpad)
    if v.get("provider") == "mwosa":
        longp = {sc["id"] for sc in script["scenes"] if sc.get("pause") == "long"}
        mpad = lambda sid, t: 0.8 if (sid in longp or t.rstrip().endswith("?")) else 0.45
        pend = [(text, os.path.join(out_dir, f"{sc['id']}_b{i + 1}_{beat_key(v, text)}.mp3"), sc["id"])
                for sc in script["scenes"] for i, text in enumerate(sc["beats"])]
        mwosa_batch(v, [x for x in pend if not os.path.exists(x[1]) or os.path.getsize(x[1]) < 1024], mpad)
    if v.get("provider") == "eleven":
        flat = [(sc["id"], i, t) for sc in script["scenes"] for i, t in enumerate(sc["beats"])]
        longp = {sc["id"] for sc in script["scenes"] if sc.get("pause") == "long"}
        padf = lambda sid, t: 0.8 if (sid in longp or t.rstrip().endswith("?")) else 0.45
        # each beat is one sentence; context = all prior / following narration (trimmed to 400 chars in eleven_fetch)
        ctx = lambda n: (" ".join(t for _, _, t in flat[:n]) or None, " ".join(t for _, _, t in flat[n + 1:]) or None)
        fname = lambda sid, i, t: f"{sid}_b{i + 1}_{gen_key(v, t)}_{master_tag(padf(sid, t))}.mp3"
        elnames = {(sid, i): fname(sid, i, t) for sid, i, t in flat}
        new, fresh = [], []
        for n, (sid, i, text) in enumerate(flat):
            p = os.path.join(out_dir, fname(sid, i, text))
            src = os.path.join(out_dir, f"{sid}_b{i + 1}_{gen_key(v, text)}.src.mp3")
            if os.path.exists(p) and os.path.getsize(p) > 1024:
                continue
            if not os.path.exists(src):
                eleven_fetch(ekey, v, text, src, *ctx(n))
                fresh.append((n, p, text))
                print("eleven", os.path.basename(src), flush=True)
            eleven_master(src, p, padf(sid, text))
            new.append((n, p, text))
        # Judge only freshly generated takes (a re-master of an already-judged take costs nothing and needs no retake)
        scores = judge([(p, t) for _, p, t in fresh], out_dir)
        retry = [(n, p, t) for n, p, t in fresh if scores[p]["sim"] < GOOD_SIM or scores[p]["wer"] > GOOD_WER]
        for n, p, t in retry:
            src = os.path.join(out_dir, f"{flat[n][0]}_b{flat[n][1] + 1}_{gen_key(v, t)}.src.mp3")
            eleven_fetch(ekey, v, t, src + ".t2", *ctx(n))
            eleven_master(src + ".t2", p + ".t2.mp3", padf(flat[n][0], t))
        s2 = judge([(p + ".t2.mp3", t) for _, p, t in retry], out_dir)
        qlog = []
        for n, p, t in fresh:
            src = os.path.join(out_dir, f"{flat[n][0]}_b{flat[n][1] + 1}_{gen_key(v, t)}.src.mp3")
            a, b = scores[p], s2.get(p + ".t2.mp3")
            if b and b["score"] > a["score"]:
                os.replace(p + ".t2.mp3", p); os.replace(src + ".t2", src); a = b
            elif b:
                os.remove(p + ".t2.mp3"); os.remove(src + ".t2")
            qlog.append({"file": os.path.basename(p), "sim": a["sim"], "wer": a["wer"], "takes": 2 if b else 1})
            print("judge", json.dumps(qlog[-1]), flush=True)
        if qlog:
            json.dump(qlog, open(os.path.join(out_dir, "_eleven_quality.json"), "w"), indent=1)
    if v.get("provider") == "clone":
        pending = []
        for sc in script["scenes"]:
            for i, text in enumerate(sc["beats"]):
                p = os.path.join(out_dir, f"{sc['id']}_b{i + 1}_{beat_key(v, text)}.mp3")
                if not os.path.exists(p) or os.path.getsize(p) < 1024:
                    pending.append((text, p))
        clone_batch(v, pending)
    for sc in script["scenes"]:
        beats = []
        for i, text in enumerate(sc["beats"]):
            h = beat_key(v, text)
            fname = elnames[(sc["id"], i)] if v.get("provider") == "eleven" else ownfiles[(sc["id"], i)] if v.get("provider") == "owner"                 else f"{sc['id']}_b{i + 1}_{h}.mp3"
            path = os.path.join(out_dir, fname)
            if v.get("provider") == "silent" and (not os.path.exists(path) or not os.path.exists(path[:-4] + ".words.json")):
                silent_beat(text, path)
            if not os.path.exists(path) or os.path.getsize(path) < (200 if v.get("provider") == "silent" else 1024):
                if v.get("provider") in ("clone", "eleven", "kokoro", "silent", "owner", "mwosa"):
                    raise RuntimeError(f"clone produced no audio for {fname}")
                key = key or api_key()
                src = path[:-4] + ".src.mp3"
                if not os.path.exists(src) or os.path.getsize(src) < 1024:
                    synth(key, v, text, src)
                    print("tts", fname)
                openai_master(src, path)
            # owner 2026-11-02: default TTS pace "a lil too slow" -> speed up with pitch-preserving atempo
            pace = float(v.get("pace", 1.0))  # pitch-preserving atempo; eleven default 1.08 keeps Shorts under 60 s
            if abs(pace - 1.0) > 0.001:
                fname = fname[:-4] + f"_p{int(round(pace * 100))}.mp3"
                paced = os.path.join(out_dir, fname)
                if not os.path.exists(paced):
                    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", path, "-af", f"atempo={pace}",
                                        "-c:a", "libmp3lame", "-q:a", "2", paced], capture_output=True, text=True, creationflags=NO_WINDOW)
                    if r.returncode:
                        raise RuntimeError(r.stderr)
                path = paced
            beats.append({"text": text, "file": f"{script['id']}/vo/{fname}", "dur": round(duration(path), 3), "words": words(path)})
        timing["scenes"].append({"id": sc["id"], "beats": beats})
    with open(os.path.join(ep_dir, "timing.json"), "w", encoding="utf-8") as f:
        json.dump(timing, f, indent=1)
    total = sum(b["dur"] for s in timing["scenes"] for b in s["beats"])
    print(f"voice total {total:.1f}s across {sum(len(s['beats']) for s in timing['scenes'])} beats")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("ep_dir")
    ap.add_argument("--engine", choices=("clone", "eleven", "auto", "kokoro", "silent", "owner", "mwosa"), default="clone")
    a = ap.parse_args()
    main(a.ep_dir, a.engine)
