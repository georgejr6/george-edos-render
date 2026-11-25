"""George Edos daily Shorts: 5 tutorials a day (Claude / ChatGPT+Codex / Grok), written, voiced, rendered and scheduled in CI.

  python tools/daily.py prepare [--n 5]      plan topics, write scripts (Groq, OpenAI fallback), voice, register compositions
  python tools/daily.py publish <ep> <slot>  upload out/<ep>.mp4 to the "George Edos" Studio brand, private + publishAt

Voice: owner 2026-11-24 chose "Narrator + OpenAI overflow": 2 Shorts/day on the ElevenLabs Studio Narrator (while the shared pool
stays above ELEVEN_FLOOR), the rest on OpenAI gpt-4o-mini-tts. Titles: tool + outcome, 3-6 words (owner: "get straight to the point").
Writers may only use the facts in tools/topics.json (no invented features, numbers or menus).
Keys (env): GROQ_API_KEY, OPENAI_API_KEY, ELEVEN_PAID_KEY, SCHED_EMAIL, SCHED_PASSWORD.
"""
import argparse, datetime as dt, json, os, re, subprocess, sys, time, urllib.error, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
STATE = os.path.join(TOOLS, "state.json")
FREE = "https://george-edos-skills.vercel.app"
API = "https://novam-scheduler-api-production.up.railway.app"
ELEVEN_FLOOR = 18000          # leave the rest of the shared ElevenLabs pool to NOVAM / DIGITVL until the monthly reset
NARRATOR_SLOTS = (1, 3)       # 11 AM and 5 PM ET get the owner's narrator voice
SLOTS_UTC = ("13:00", "16:00", "19:00", "22:00", "01:00")   # 8 AM, 11 AM, 2 PM, 5 PM, 8 PM ET (01:00 = next day)
ANGLES = ("how-to", "mistake", "tips")
ROTATION = ("claude", "chatgpt", "grok", "claude", "chatgpt")
MUSIC = ("music/investigation_air.mp3", "music/investigation_beginning.mp3", "music/resolution_dreams.mp3")
CREDIT = {"music/investigation_air.mp3": "Ossuary 6 - Air", "music/investigation_beginning.mp3": "Ossuary 1 - A Beginning",
          "music/resolution_dreams.mp3": "Dreams Become Real"}
NAME = {"claude": "Claude", "chatgpt": "ChatGPT", "grok": "Grok"}
TITLE_WORDS = {"claude": ("Claude",), "chatgpt": ("ChatGPT", "Codex"), "grok": ("Grok",)}
OAI_VOICE = {"provider": "openai", "model": "gpt-4o-mini-tts", "voice": "cedar", "pace": 1.05,
             "instructions": "Calm, clear tech tutorial narrator. Confident and friendly, natural conversational delivery, slightly brisk pace."}
GROQ = ("https://api.groq.com/openai/v1/chat/completions", "GROQ_API_KEY")
OAI = ("https://api.openai.com/v1/chat/completions", "OPENAI_API_KEY")
MODELS = [(OAI, "gpt-4.1"), (GROQ, "openai/gpt-oss-120b"), (OAI, "gpt-4.1-mini")]   # writer: gpt-4.1 follows the fact rules best (~2 cents a Short)


def load_state():
    return json.load(open(STATE)) if os.path.exists(STATE) else {"next": 4, "done": [], "rot": 0}


def plan(n, state):
    topics = json.load(open(os.path.join(TOOLS, "topics.json"), encoding="utf-8"))
    done = set(state["done"])
    out = []
    for k in range(n):
        tool = ROTATION[(state["rot"] + k) % len(ROTATION)]
        pick = None
        for angle in ANGLES:  # every topic gets the how-to first, then the mistake angle, then quick tips
            pick = next((dict(t, angle=angle) for t in topics if t["tool"] == tool and f"{t['topic']}|{angle}" not in done
                         and all(o["topic"] != t["topic"] for o in out)), None)
            if pick:
                break
        if not pick:
            sys.exit(f"topic bank exhausted for {tool}: add topics to tools/topics.json")
        done.add(f"{pick['topic']}|{pick['angle']}")
        out.append(pick)
    return out


# ------------------------------------------------------------------ writer
SCHEMA = """Output ONE JSON object: {"title": str, "scenes": [scene, ...]}.
scene = {"id": "a".."f", "beats": [1-3 spoken sentences], "card": card, "pills"?: [{"text": str<=28 chars, "beat": int, "tone"?: "red"|"green"}], "red"?: [caption accent words]}
card is one of:
 {"type":"title","kicker":"<TOOL> TIP","line1":"<=18 chars white","line2":"<=18 chars accent","sub":""}
 {"type":"terminal","title":"terminal"|"claude"|"chatgpt"|"codex"|"grok"|"<FILE>.md","numbers"?:bool,"carry"?:"<earlier scene id>","lines":[{"k":kind,"t":"<=48 chars","beat":int}]}
   kinds: "cmd" (typed shell command), "user" (what the person types to the AI), "claude" (the AI's reply, for ANY assistant), "file" (file contents), "out" (program output), "ok" (success line)
 {"type":"list","title":"<=24 chars","items":[{"t":"<=26 chars","beat":int,"ok"?:true,"x"?:true}]}   (2-4 items)
 {"type":"flow","nodes":[{"t":"<=18 chars","s":"","beat":int}]}   (3 nodes)
 {"type":"compare","bad":{"t":"<=60 chars","beat":int,"label":"BAD"},"good":{"t":"<=80 chars","beat":int,"label":"GOOD"}}
"beat" = index into that scene's beats (0-based) when the item appears."""

STYLE = """You write 40-second faceless YouTube Shorts tutorials for the channel "George Edos" (AI tools tutorials).
Voice: plain, confident, short declarative sentences (6-16 words). Spoken aloud by a narrator. No hype words, no emojis, no questions to the viewer except maybe the hook.
Structure: 4-5 scenes. Scene a = hook (the problem, in one punchy line + one supporting line). Middle scenes = the steps, shown on screen. Last scene = the payoff (what you get).
Do NOT write a call to action or "follow" line; it is added automatically.
Total spoken words across all beats: 80-115.
Write file names and commands the way they are SAID in beats: "CLAUDE dot M D", "AGENTS dot M D", "slash compact". On screen (card text) write them normally: CLAUDE.md, /compact.
Every sentence must teach, show or prove something. No filler that restates ("This ensures...", "This makes it easy...", "smarter and tailored"). No "Want to...?" or "Tired of...?" openers.
Hook (scene a, first beat): a blunt statement of the pain or the payoff, 4-10 words, e.g. "Claude forgets your project every single time." or "Your ChatGPT answers are generic for one reason."
Show it: at least two scenes must be terminal or chat screens with the exact thing the viewer types or sees.
You MAY invent example content the viewer would type themselves (a sample rule, a sample prompt, a sample question).
Use ONLY the facts provided for anything about how the tool works. Never invent menu names, button names, prices, version numbers, statistics or features that are not in the facts. If a detail is not in the facts, leave it out.
Never describe the screen or UI (where to click, tabs, fields, boxes, status bars, what appears, what to type to confirm) beyond the exact words in the facts. If the facts do not say how to switch something on, just say "turn on X" and never describe how. Never claim what the AI will reply or how its output is structured. Keep steps at the level of the facts: e.g. "Open settings, then Personalization." not "Click the gear icon in the top corner."
Title: 3-6 words, Title Case, straight to the point: tool name + outcome (e.g. "Make Claude Remember You", "Stop Claude Making Up Numbers"). Never use the words Tutorial, How-To, Guide, Explained, or Feature in a title. No "#", no "This one", no "The #1".
"""

ANGLE = {"how-to": "Angle: a straight how-to. Show how to do it, step by step.",
         "mistake": "Angle: the common mistake. Open with what people get wrong, then show the right way.",
         "tips": "Angle: quick tips. Give 3 short numbered tips drawn from the facts."}


def chat(messages, models=None):
    last = None
    for (url, keyname), model in (models or MODELS):
        key = os.environ.get(keyname)
        if not key:
            continue
        body = {"model": model, "messages": messages, "temperature": 0.7, "response_format": {"type": "json_object"}, "max_tokens": 6000}
        req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "User-Agent": "ge-daily/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.loads(r.read())["choices"][0]["message"]["content"], model
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 429 and url == GROQ[0]:
                time.sleep(25)  # per-minute token cap: one wait, then retry this model once
                try:
                    with urllib.request.urlopen(req, timeout=180) as r:
                        return json.loads(r.read())["choices"][0]["message"]["content"], model
                except Exception as e2:  # noqa: BLE001
                    last = e2
            print("writer fallback:", model, getattr(last, "code", last), flush=True)
        except (urllib.error.URLError, TimeoutError, KeyError) as e:
            last = e
            print("writer fallback:", model, getattr(e, "code", e), flush=True)
    raise RuntimeError(f"no writer model worked: {last}")


def validate(d, item):
    err = []
    title = (d.get("title") or "").strip()
    if not 3 <= len(title.split()) <= 6:
        err.append(f"title must be 3-6 words (got {len(title.split())})")
    if not any(w.lower() in title.lower() for w in TITLE_WORDS[item["tool"]]):
        err.append(f"title must contain {' or '.join(TITLE_WORDS[item['tool']])}")
    if re.search(r"(tutorial|how-to|how to use|guide|explained|feature)", title, re.I):
        err.append("title must state the outcome, not 'tutorial/how-to/guide'")
    if "#" in title:
        err.append("no # in title")
    scenes = d.get("scenes") or []
    if not 3 <= len(scenes) <= 6:
        err.append("need 3-6 scenes")
    words = 0
    facts = " ".join(item["facts"])
    for sc in scenes:
        b = sc.get("beats") or []
        if not 1 <= len(b) <= 4 or not all(isinstance(x, str) and x.strip() for x in b):
            err.append(f"scene {sc.get('id')}: 1-4 non-empty beats"); continue
        words += sum(len(x.split()) for x in b)
        for x in b:
            if len(x.split()) > 22:
                err.append(f"scene {sc.get('id')}: beat too long ({len(x.split())} words)")
            for num in re.findall(r"\d[\d,.%]*", x):
                if num.strip(".,") not in facts and int(re.sub(r"\D", "", num) or 0) > 5:
                    err.append(f"number {num} is not in the facts")
        c = sc.get("card") or {}
        t = c.get("type")
        if t not in ("title", "terminal", "list", "flow", "compare"):
            err.append(f"scene {sc.get('id')}: bad card type {t}"); continue
        nb = len(b)
        beats = [x.get("beat", 0) for x in c.get("lines", []) + c.get("items", []) + c.get("nodes", [])]
        beats += [c[k].get("beat", 0) for k in ("bad", "good") if isinstance(c.get(k), dict)]
        beats += [p.get("beat", 0) for p in sc.get("pills", [])]
        if any(not isinstance(x, int) or x < 0 or x >= nb for x in beats):
            err.append(f"scene {sc.get('id')}: a beat index is out of range (scene has {nb} beats)")
        if t == "terminal" and not 1 <= len(c.get("lines", [])) <= 8:
            err.append(f"scene {sc.get('id')}: terminal needs 1-8 lines")
        if any(len(l.get("t", "")) > 60 for l in c.get("lines", [])):
            err.append(f"scene {sc.get('id')}: terminal line over 60 chars")
        if t == "list" and not 2 <= len(c.get("items", [])) <= 4:
            err.append(f"scene {sc.get('id')}: list needs 2-4 items")
        if t == "compare" and not (isinstance(c.get("bad"), dict) and isinstance(c.get("good"), dict)):
            err.append(f"scene {sc.get('id')}: compare needs bad and good")
        if any(len(p.get("text", "")) > 32 for p in sc.get("pills", [])):
            err.append(f"scene {sc.get('id')}: pill text over 32 chars")
        if c.get("carry") and c["carry"] not in [s.get("id") for s in scenes]:
            del c["carry"]
    if not 70 <= words <= 125:
        err.append(f"total spoken words must be 80-115 (got {words})")
    if re.search(r"\b(follow (for|me|us|along)|subscribe|link in (the )?(bio|description))\b", " ".join(x for sc in scenes for x in sc.get("beats", [])), re.I):
        err.append("no call to action; it is added automatically")
    return err


CHECKER = [(("https://api.openai.com/v1/chat/completions", "OPENAI_API_KEY"), "gpt-4.1"), (GROQ, "openai/gpt-oss-120b")]


def factcheck(d, item):
    """Second model lists every claim about how the tool works that the facts do not support. Example user input is fine."""
    lines = [x for sc in d["scenes"] for x in sc["beats"]]
    for sc in d["scenes"]:
        c = sc.get("card") or {}
        lines += [l.get("t", "") for l in c.get("lines", []) if l.get("k") in ("claude", "out", "ok")]  # what the tool "shows"
        lines += [it.get("t", "") for it in c.get("items", [])] + [p.get("text", "") for p in sc.get("pills", [])]
    lines = [x for x in lines if x.strip()]
    prompt = (f"Tool: {NAME[item['tool']]}\nFACTS (verified true):\n- " + "\n- ".join(item["facts"]) +
              "\n\nLabel EVERY numbered line of a tutorial script with one label:\n"
              "FACT = says the same thing as a FACT, or a plain implication of it (names that appear in the FACTS are fine).\n"
              "STEP = a generic action that is true for any app (open settings, start a new chat, type your question, save the file).\n"
              "EXAMPLE = sample text the viewer would type or put in a file.\n"
              "FRAMING = the problem or the benefit in general words (it forgets you, you stop repeating yourself, saves time).\n"
              "INVENTED = any other concrete claim about the tool: a button, field, tab, status bar, label, keyword, command, shortcut, "
              "how to confirm, what the tool replies or shows, how its output is structured, speed, accuracy, or a capability not in the FACTS.\n"
              "When unsure between INVENTED and anything else, choose INVENTED.\n\nLINES:\n" +
              "\n".join(f"{i + 1}. {x}" for i, x in enumerate(lines)) +
              '\n\nReturn JSON: {"labels": [{"n": 1, "label": "FACT", "why": "short reason"}]}')
    raw, _ = chat([{"role": "user", "content": prompt}], CHECKER)
    try:
        bad = [x for x in json.loads(raw).get("labels", []) if str(x.get("label", "")).upper() == "INVENTED"]
    except (json.JSONDecodeError, AttributeError):
        return ["fact check could not be parsed; rewrite more plainly"]
    return [f'line not supported by the facts, remove or reword it: "{lines[x["n"] - 1]}" ({x.get("why", "")})'
            for x in bad if isinstance(x.get("n"), int) and 0 < x["n"] <= len(lines)][:8]


def write(ep, item, music):
    msgs = [{"role": "system", "content": STYLE + "\n" + SCHEMA},
            {"role": "user", "content": f"Tool: {NAME[item['tool']]}\nTopic: {item['topic']}\n{ANGLE[item['angle']]}\nFacts (the only facts you may use):\n- "
             + "\n- ".join(item["facts"]) + "\n\nReturn the JSON object only."}]
    for attempt in range(5):
        raw, model = chat(msgs)
        try:
            d = json.loads(raw)
            err = validate(d, item)
            if not err and "george" in json.dumps(d).lower():
                err = ["never use the word George anywhere in the script"]
            if not err:
                err = factcheck(d, item)
        except (json.JSONDecodeError, AttributeError, TypeError) as e:
            d, err = None, [f"invalid JSON: {e}"]
        if not err:
            break
        print(ep, "retry", attempt + 1, err[:6], flush=True)
        msgs += [{"role": "assistant", "content": raw}, {"role": "user", "content": "Fix these problems and return the full JSON again:\n- " + "\n- ".join(err)}]
    else:
        raise RuntimeError(f"{ep}: writer failed validation: {err}")
    for i, sc in enumerate(d["scenes"]):
        sc["id"] = "abcdef"[i]
        sc.pop("hold", None)
    tool = item["tool"]
    d["scenes"].append({"id": "end", "beats": [f"Follow for a new {NAME[tool] if tool != 'chatgpt' else 'AI'} tutorial every day."],
                        "card": {"type": "cta", "line1": "Daily AI tutorials", "line2": FREE.replace("https://", ""), "tag": "FREE SKILL PACK IN THE DESCRIPTION", "items": []},
                        "hold": 0.8})
    script = {"id": ep, "format": "tutorial-short", "kind": "short", "tool": tool, "title": d["title"].strip(), "music": music, "musicVol": 0.12,
              "url": FREE, "scenes": d["scenes"], "topic": item["topic"], "angle": item["angle"], "writer": model}
    os.makedirs(os.path.join(ROOT, "episodes", ep), exist_ok=True)
    json.dump(script, open(os.path.join(ROOT, "episodes", ep, "script.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    open(os.path.join(ROOT, "episodes", ep, "Video.tsx"), "w").write(
        'import script from "./script.json";\nimport timing from "./timing.json";\nimport { makeTutorial, TScript } from "../../src/kit/tutorial";\n'
        'import { Timing } from "../../src/kit/timeline";\n\nexport const { Comp: Video, built } = makeTutorial(script as unknown as TScript, timing as Timing);\n')
    print(ep, "written by", model, "|", script["title"], flush=True)
    return script


# ------------------------------------------------------------------ voice + registry
def eleven_left():
    key = os.environ.get("ELEVEN_PAID_KEY")
    if not key:
        return 0
    try:
        req = urllib.request.Request("https://api.elevenlabs.io/v1/user/subscription", headers={"xi-api-key": key})
        d = json.loads(urllib.request.urlopen(req, timeout=30).read())
        return d["character_limit"] - d["character_count"]
    except Exception as e:  # noqa: BLE001
        print("elevenlabs check failed:", e)
        return 0


def voice(ep, narrator):
    p = os.path.join(ROOT, "episodes", ep, "script.json")
    s = json.load(open(p, encoding="utf-8"))
    if not narrator:
        s["voice"] = OAI_VOICE
    json.dump(s, open(p, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    r = subprocess.run([sys.executable, os.path.join(TOOLS, "tts.py"), f"episodes/{ep}", "--engine", "eleven" if narrator else "auto"], cwd=ROOT)
    if r.returncode:
        raise RuntimeError(f"{ep}: tts failed")


def register():
    """src/Root.tsx = every episode folder that has script + timing (originals keep their exported names)."""
    eps = sorted(e for e in os.listdir(os.path.join(ROOT, "episodes"))
                 if all(os.path.exists(os.path.join(ROOT, "episodes", e, f)) for f in ("script.json", "timing.json", "Video.tsx")))
    imp, comp = [], []
    for e in eps:
        src = open(os.path.join(ROOT, "episodes", e, "Video.tsx")).read()
        name = re.search(r"Comp: (\w+)", src).group(1)
        kind = json.load(open(os.path.join(ROOT, "episodes", e, "script.json"), encoding="utf-8"))["kind"]
        imp.append(f'import {{ {name} as C_{e}, built as b_{e} }} from "../episodes/{e}/Video";')
        w, h = (1920, 1080) if kind == "long" else (1080, 1920)
        comp.append(f'    <Composition id="{e.upper()}" component={{C_{e}}} durationInFrames={{b_{e}.total}} fps={{FPS}} width={{{w}}} height={{{h}}} />')
    open(os.path.join(ROOT, "src", "Root.tsx"), "w").write(
        'import React from "react";\nimport { Composition } from "remotion";\n' + "\n".join(imp) + '\nimport { FPS } from "./kit/timeline";\n\n'
        "export const Root: React.FC = () => (\n  <>\n" + "\n".join(comp) + "\n  </>\n);\n")


def slots(n):
    now = dt.datetime.now(dt.timezone.utc)
    day = now.date() if now.hour < 11 else now.date() + dt.timedelta(days=1)
    out = []
    for i, hm in enumerate(SLOTS_UTC[:n]):
        h, m = map(int, hm.split(":"))
        d = day + dt.timedelta(days=1) if h < 6 else day
        out.append(dt.datetime(d.year, d.month, d.day, h, m, tzinfo=dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    return out


def prepare(n):
    state = load_state()
    items = plan(n, state)
    left = eleven_left()
    print("elevenlabs chars left:", left, flush=True)
    made, when = [], slots(n)
    for i, item in enumerate(items):
        ep = f"gs{state['next']:03d}"
        try:
            write(ep, item, MUSIC[(state["next"] + i) % len(MUSIC)])
            narr = i in NARRATOR_SLOTS and left - 900 > ELEVEN_FLOOR
            voice(ep, narr)
            if narr:
                left -= sum(len(b) for sc in json.load(open(os.path.join(ROOT, "episodes", ep, "script.json"), encoding="utf-8"))["scenes"] for b in sc["beats"])
            made.append({"ep": ep, "slot": when[i], "voice": "narrator" if narr else "openai"})
            state["done"].append(f"{item['topic']}|{item['angle']}")
        except Exception as e:  # noqa: BLE001  one bad Short never blocks the other four
            print("SKIP", ep, e, flush=True)
        state["next"] += 1
    state["rot"] = (state["rot"] + n) % len(ROTATION)
    json.dump(state, open(STATE, "w"), indent=1)
    register()
    json.dump(made, open(os.path.join(ROOT, "out_batch.json"), "w"))
    print(json.dumps(made))
    return made


# ------------------------------------------------------------------ publish
def call(method, path, token=None, body=None):
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read() or b"{}")


def put_file(token, path, ctype):
    p = call("POST", "/api/media/presign", token, {"filename": os.path.basename(path), "contentType": ctype, "folder": "originals"})
    with open(path, "rb") as f:
        req = urllib.request.Request(p["putUrl"], data=f.read(), method="PUT", headers={"Content-Type": ctype})
    with urllib.request.urlopen(req, timeout=1800) as r:
        assert r.status in (200, 201), r.status
    return p["publicUrl"]


def description(s):
    hook = s["scenes"][0]["beats"][0]
    music = (f'Music: "{CREDIT[s["music"]]}" Kevin MacLeod (incompetech.com)\n'
             "Licensed under Creative Commons: By Attribution 4.0 License\nhttp://creativecommons.org/licenses/by/4.0/")
    tail = ("Built with tools from Novam: https://novam.us\n"
            "Not affiliated with Anthropic, OpenAI or xAI. Claude, ChatGPT, Codex and Grok are trademarks of their owners.")
    tags = {"claude": "#Claude #ClaudeCode #AI", "chatgpt": "#ChatGPT #Codex #AI", "grok": "#Grok #xAI #AI"}[s.get("tool", "claude")]
    return f"{hook}\n\nFree Claude skill + the full pack: {FREE}\n\n{music}\n\n{tail}\n\n#Shorts {tags}"


def publish(ep, slot):
    s = json.load(open(os.path.join(ROOT, "episodes", ep, "script.json"), encoding="utf-8"))
    title = s["title"] + " #Shorts"
    desc = description(s)
    if "george" in (desc + title).lower().replace(FREE, "").replace("george edos", ""):
        sys.exit("the word George appears outside the channel name")
    video = os.path.join(ROOT, "out", f"{ep}.mp4")
    token = call("POST", "/api/auth/login", body={"email": os.environ["SCHED_EMAIL"], "password": os.environ["SCHED_PASSWORD"]})["token"]
    brands = call("GET", "/api/brands", token)
    brands = brands.get("brands", brands) if isinstance(brands, dict) else brands
    brand = next(b for b in brands if b["name"].strip().lower() == "george edos")
    url = put_file(token, video, "video/mp4")
    post = call("POST", "/api/posts", token, {"brandId": brand["id"], "platform": "youtube", "title": title, "description": desc, "hashtags": [],
                                               "status": "DRAFT", "mediaUrl": url, "mediaType": "video"})
    post = post.get("post", post)
    body = {"privacy": "private", "publishAt": slot}
    print(call("POST", f"/api/posts/{post['id']}/publish-now", token, body))
    print("queued", ep, post["id"], slot, title)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("prepare", "publish", "register", "plan"))
    ap.add_argument("args", nargs="*")
    ap.add_argument("--n", type=int, default=5)
    a = ap.parse_args()
    if a.cmd == "prepare":
        prepare(a.n)
    elif a.cmd == "register":
        register()
    elif a.cmd == "plan":
        print(json.dumps(plan(a.n, load_state()), indent=1)); print(slots(a.n))
    else:
        publish(a.args[0], a.args[1])
