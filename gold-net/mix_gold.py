#!/usr/bin/env python3
"""Mix for 'Gold or a fishing net?' (stdlib + ffmpeg only).
usage: python3 mix_gold.py SILENT.mp4 timings.json OUT.mp4
timings.json: {"lines": [start of script line 1..15 in voice.mp3 seconds], "gap_before": 14, "gap": 1.4}
The video must already contain the gap (a held shot of `gap` seconds right before line `gap_before`).
Files expected next to this script: voice.mp3, bomba.mp3, sfx/*.mp3, music.mp3 (Hitman, Kevin MacLeod)."""
import json, sys, os, subprocess
H = os.path.dirname(os.path.abspath(__file__))
vid, tj, out = sys.argv[1:4]
T = json.load(open(tj)); L = T["lines"]; GB = T.get("gap_before", 14); GAP = T.get("gap", 1.4)
cut = L[GB - 1]
def vt(t): return t + GAP if t >= cut - 1e-3 else t   # voice time -> video time
def at(line, off): return vt(L[line - 1] + off) if off >= 0 or line == 1 else vt(L[line - 1]) + off
# (sfx, line, offset s, gain, max length s)
EV = [("crashzoom", 1, 0.0, .7, 2), ("pops", 1, 1.0, .45, 1),
      ("wave", 2, 0.0, .55, 1), ("pops", 2, 1.5, .4, 1),
      ("goldburst", 3, 0.3, .8, 1), ("sunglasses", 3, 0.8, .55, 2),
      ("crickets", 4, 0.5, .35, 2), ("laugh", 4, 1.0, .4, 2),
      ("kaching", 5, 0.5, .5, 1.4), ("pops", 5, 1.1, .4, 1),
      ("fishflop", 6, 0.7, .55, 1.5), ("trombone", 6, 1.1, .5, 1),
      ("counter", 7, 1.1, .5, 2),
      ("emptychest", 8, 0.4, .6, 1),
      ("toothcrack", 9, 0.7, .8, 2),
      ("pops", 10, 0.3, .5, 1), ("pops", 10, 1.1, .5, 1), ("pops", 10, 1.9, .5, 1),
      ("bassdrop", 11, 0.0, 1.0, 1.1),
      ("crawl", 12, 0.0, .5, 1),
      ("moth", 14, 0.6, .5, 2),
      ("riser", 15, 1.0, .6, 1)]
dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", vid],
                           capture_output=True, text=True).stdout)
ins = ["-i", vid, "-i", f"{H}/voice.mp3", "-stream_loop", "-1", "-i", f"{H}/music.mp3", "-i", f"{H}/bomba.mp3"]
fc = []
# voice with inserted gap
fc.append(f"[1:a]aresample=44100,aformat=channel_layouts=stereo,asplit=2[va][vb];[va]atrim=0:{cut},asetpts=PTS-STARTPTS[v1];"
          f"[vb]atrim=start={cut},asetpts=PTS-STARTPTS[v2];"
          f"anullsrc=r=44100:cl=stereo,atrim=0:{GAP}[vg];"
          f"[v1][vg][v2]concat=n=3:v=0:a=1,apad,atrim=0:{dur},asplit=2[voice][sc]")
# music: Hitman from 58 s, muted for the glow-up hit, ducked under voice
g0, g1 = at(11, 0.0), at(11, 0.0) + 1.5
fc.append(f"[2:a]atrim=start=58,asetpts=PTS-STARTPTS,aresample=44100,atrim=0:{dur},volume=0.30,"
          f"volume='if(between(t,{g0:.3f},{g1:.3f}),0,1)':eval=frame,afade=t=out:st={dur - 0.6:.3f}:d=0.6[m0];"
          "[m0][sc]sidechaincompress=threshold=0.03:ratio=6:attack=15:release=350[music]")
mix = ["[voice]", "[music]"]; k = 4
for i, (n, line, off, g, mx) in enumerate(EV):
    ins += ["-i", f"{H}/sfx/{n}.mp3"]; t = max(0, at(line, off))
    fc.append(f"[{k}:a]aresample=44100,atrim=0:{mx},volume={g},adelay={int(t * 1000)}:all=1[s{i}]"); mix.append(f"[s{i}]"); k += 1
# Desmond: 'Bomba-' then BEEP, inside the gap before line 14
tb = cut + 0.15
fc.append(f"[3:a]aresample=44100,atrim=0:0.88,afade=t=out:st=0.84:d=0.04,adelay={int(tb * 1000)}:all=1[bm]"); mix.append("[bm]")
fc.append(f"sine=f=1000:d=0.45:r=44100,volume=0.3,afade=t=in:d=0.005,afade=t=out:st=0.44:d=0.01,adelay={int((tb + 0.88) * 1000)}:all=1[bp]"); mix.append("[bp]")
fc.append("".join(mix) + f"amix=inputs={len(mix)}:normalize=0:duration=longest,atrim=0:{dur},loudnorm=I=-14:TP=-1.5:LRA=11[a]")
subprocess.run(["ffmpeg", "-y", "-loglevel", "error"] + ins + ["-filter_complex", ";".join(fc), "-map", "0:v", "-map", "[a]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", str(dur), out], check=True)
print("ok", out)
print('CREDIT:\nMusic: "Hitman" by Kevin MacLeod (incompetech.com)\nLicensed under Creative Commons: By Attribution 4.0\nhttp://creativecommons.org/licenses/by/4.0/')
