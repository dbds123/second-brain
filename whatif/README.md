# Coin Island "What if" format (from 14.11.2026)

Plan: https://claude.ai/artifact/8WS9yJF796nNHk4FCAQF3C (Daniel chose "Plan wie empfohlen starten", 14.11. 00:23 Berlin).
Two shorts/day from Mon 16.11. at 18:00 and 21:00 Berlin (only free slots). Kill rule: >50k views in 48 h -> 3 follow-ups in 72 h; twice <5k -> end format.

Reusable scene idea: island set from gta6/brick-tax Blender builds + a HUD counter (big number top third, timer chip "T+12s") drawn in post (PIL), so every episode only swaps the counter curve + shots.
Every episode has its own story, own escalation and own punchline (no template repetition).

Episodes: 01-money-doubles, 02-dollar-since-pyramids, then 03 heavier coin, 04 everyone gets $1M, 05 one cent doubled daily, 06 prices double every 4 days.

## Status 14.11. 00:35 Berlin
- Scripts: 01-money-doubles/skript-v1.md, 02-dollar-since-pyramids/skript-v1.md (numbers recomputed; #2 year one = 2,560 years after 2560 BC, no year zero).
- Voices: Titan take A (eleven_v4). Flows: #1 LAMWhReIXbwQZ8GjZQGe, #2 P4bO5kGdxpnnmGfRZw1n. voice/voice-tight.wav has a 1.3 s Bomba gap (#1 at 28.16 s, #2 at 37.96 s). Lengths 48.1 s and 45.2 s (kept long on purpose: the #1 narration lands each number on the real clock).
- Word timings: voice/words.json (Scribe, before the gap).
- kit/whatif_hud.py + kit/Nunito.ttf: reusable counter HUD (gold number, unit label, timer/year chip, red comparison stamps). Each episode has hud_ep.py (KEYS video t -> story clock, value fn, tags). Preview: python3 kit/whatif_hud.py <episode dir> 1 10 20 -> hud_preview.png. In post.py: img = overlay(img, hud(t, EP, W, HH)).
- Next: Blender scene on the Mac (copy gta6 world, add coin-pile growth driven by the same KEYS), render #1 + #2, mix with music-free/addmusic.py.
- 14.11. 01:35 Berlin: Daniel wants something other than "Bombaclat". Proposed (card): seagull thief hidden in every episode + end line "Did you spot the seagull?" (recommended), Desmond's calculator explodes, Squid "...and?". The 1.3 s gap in voice-tight.wav stays as the slot for the new gag.
- 14.11. 01:35 Berlin DECISION (Daniel "ja 2 ist gut", wants social-media brainrot, not tame gags): no more "Bomba". Running gag = SQUID SIGMA MODE at the biggest number: Squid slowly lowers his sunglasses, phonk drop (own SFX, no copied track), glowing eyes, hard cut back. Goes into the 1.3 s gap (#1 before "Thirty seconds: one billion", #2 after "145 billion dollars").
- 14.11. 01:39 Berlin: Daniel picked kit/phonk/phonk-3.mp3 for the Squid sigma moment and also wants the bass drop from phonk-2.mp3 kept in the kit (use as impact under big number reveals). Both are own ElevenLabs Music generations (flow KqTKKkvyvjkwussLEBka), no credit needed, no Content ID risk.
