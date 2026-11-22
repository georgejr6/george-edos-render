"""Original (synthesised) UI sound effects for the George Edos render repo: pop.wav, whoosh.wav, hit_low.wav.
Run once: python tools/make_sfx.py  (numpy only). No third-party audio, so there is nothing to license."""
import os, wave
import numpy as np

SR = 44100
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "public", "sfx")


def save(name, y):
    y = y / (np.abs(y).max() + 1e-9) * 0.9
    n = len(y)
    f = int(SR * 0.004)
    y[:f] *= np.linspace(0, 1, f)
    y[-f:] *= np.linspace(1, 0, f)
    with wave.open(os.path.join(OUT, name), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((y * 32767).astype(np.int16).tobytes())


rng = np.random.default_rng(11)
t = np.arange(int(SR * 0.22)) / SR
# pop: quick pitch-dropping sine
f0 = 900 * np.exp(-t * 14) + 380
save("pop.wav", np.sin(2 * np.pi * np.cumsum(f0) / SR) * np.exp(-t * 20))
# whoosh: band-passed noise swept up then down
t = np.arange(int(SR * 0.55)) / SR
noise = rng.standard_normal(len(t))
k = np.exp(-((t - 0.22) ** 2) / (2 * 0.1 ** 2))
lp = np.zeros_like(noise)
a = 0.03 + 0.5 * k
for i in range(1, len(noise)):
    lp[i] = lp[i - 1] + a[i] * (noise[i] - lp[i - 1])
save("whoosh.wav", lp * k)
# low hit: sub thump with a short noise transient
t = np.arange(int(SR * 1.2)) / SR
f0 = 95 * np.exp(-t * 3) + 42
body = np.sin(2 * np.pi * np.cumsum(f0) / SR) * np.exp(-t * 4.2)
click = rng.standard_normal(len(t)) * np.exp(-t * 90) * 0.35
save("hit_low.wav", body + click)
print("ok", OUT)
