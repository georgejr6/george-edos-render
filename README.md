# George Edos render

Remotion project that renders the George Edos Claude tutorials (long + Shorts) on free GitHub Actions runners.
`gh workflow run render.yml -f episode=gs01 -f chunks=1` (Shorts) or `-f episode=ge01 -f chunks=3` (long).
Narration mp3s are release assets `vo-<episode>`; output is release asset `render-<episode>`.
Sound effects are synthesised by `tools/make_sfx.py`; music is Kevin MacLeod (incompetech.com, CC BY 4.0).
