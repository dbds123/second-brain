# Reusable "What if" counter HUD for Coin Island shorts (drop-in for post.py of the Blender builds).
# Each episode passes an EP dict:
#   KEYS   : [(video_t, story_x), ...] piecewise-linear, monotonic; maps video time -> story clock
#   value  : f(story_x) -> number shown in the big counter
#   unit   : small label above the number ("COINS", "$")
#   chip   : f(story_x) -> text of the chip under the number ("T+12s", "2560 BC")
#   tags   : [(t0, t1, "≈ 1 ELEPHANT"), ...] comparison stamps under the chip
#   show   : (t0, t1) when the HUD is visible
# hud(t, EP, W, H) -> (rgb float32 HxWx3, alpha HxWx1) or None. Same layer format as post.py overlay().
import os, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
FONTP = os.path.join(HERE, "Nunito.ttf")
GOLD, GOLD_HI, INK = (255, 205, 60), (255, 240, 170), (40, 22, 8)
_fc = {}

def font(px):
    px = max(8, int(px))
    if px not in _fc:
        f = ImageFont.truetype(FONTP, px)
        try: f.set_variation_by_name("Black")
        except Exception: pass
        _fc[px] = f
    return _fc[px]

def story(t, keys, log=False):
    if t <= keys[0][0]: return keys[0][1]
    for (a, x0), (b, x1) in zip(keys, keys[1:]):
        if a <= t <= b:
            u = (t - a) / (b - a)
            if log and x0 > 0 and x1 > 20 * x0:          # exponential ramp: the counter accelerates smoothly
                return x0 * (x1 / x0) ** u
            return x0 + (x1 - x0) * u
    return keys[-1][1]

def fmt(v):
    v = int(round(v))
    return f"{v:,}"

def _text(d, xy, s, f, fill, stroke, sw, anchor="mm"):
    d.text(xy, s, font=f, anchor=anchor, fill=fill, stroke_width=sw, stroke_fill=stroke)

def hud(t, EP, W=1080, H=1920):
    t0, t1 = EP.get("show", (0, 1e9))
    if t < t0 or t > t1: return None
    k = W / 1080
    al = min(1.0, (t - t0) / 0.15) * min(1.0, (t1 - t) / 0.25)
    x = story(t, EP["KEYS"], EP.get("log", False))
    v = EP["value"](x)
    s = EP.get("fmt", fmt)(v)
    # pulse whenever the shown string changes (approx: on each whole story step)
    frac = x - math.floor(x)
    pulse = 1.0 + 0.22 * math.exp(-frac * 10) if EP.get("pulse", True) else 1.0
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    cy = EP.get("y", 330) * k
    # number: shrink to fit 92% width
    size = 170 * k
    while size > 40 and d.textlength(s, font=font(size)) > 0.92 * W:
        size *= 0.93
    f = font(size * pulse)
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ds = ImageDraw.Draw(sh)
    _text(ds, (W / 2, cy + 12 * k), s, f, (0, 0, 0, 170), (0, 0, 0, 170), int(12 * k))
    sh = sh.filter(ImageFilter.GaussianBlur(10 * k))
    lay.alpha_composite(sh)
    _text(d, (W / 2, cy), s, f, GOLD, INK, max(3, int(10 * k)))
    # specular sweep: thin highlight band on top half of the digits
    hi = Image.new("L", (W, H), 0); dh = ImageDraw.Draw(hi)
    _text(dh, (W / 2, cy), s, f, 255, 0, 0)
    band = Image.new("L", (W, H), 0); db = ImageDraw.Draw(band)
    bb = d.textbbox((W / 2, cy), s, font=f, anchor="mm")
    db.rectangle([0, bb[1], W, bb[1] + (bb[3] - bb[1]) * 0.42], fill=110)
    hl = Image.composite(Image.new("RGBA", (W, H), GOLD_HI + (255,)), Image.new("RGBA", (W, H), (0, 0, 0, 0)),
                         Image.fromarray(np.minimum(np.asarray(hi), np.asarray(band)).astype(np.uint8)))
    lay.alpha_composite(hl)
    # unit label above
    if EP.get("unit"):
        nb0 = d.textbbox((W / 2, cy), s, font=font(size), anchor="mm")
        _text(d, (W / 2, nb0[1] - 48 * k), EP["unit"], font(58 * k), (255, 255, 255, 255), INK, int(6 * k))
    # chip below (timer / year)
    if EP.get("chip"):
        cs = EP["chip"](x)
        cf = font(54 * k)
        tw = d.textlength(cs, font=cf)
        nb = d.textbbox((W / 2, cy), s, font=font(size), anchor="mm")
        ccy = nb[3] + 62 * k
        d.rounded_rectangle([W / 2 - tw / 2 - 28 * k, ccy - 40 * k, W / 2 + tw / 2 + 28 * k, ccy + 40 * k], radius=40 * k,
                            fill=(20, 12, 6, 200), outline=(255, 205, 60, 255), width=max(2, int(4 * k)))
        _text(d, (W / 2, ccy), cs, cf, (255, 255, 255, 255), (0, 0, 0, 0), 0)
        # comparison stamp
        for a, b, tag in EP.get("tags", []):
            if a <= t <= b:
                u = (t - a)
                sc = 1.0 + 0.5 * math.exp(-u * 12)
                tf = font(64 * k * sc)
                rot = Image.new("RGBA", (W, int(200 * k)), (0, 0, 0, 0)); dr = ImageDraw.Draw(rot)
                _text(dr, (W / 2, 100 * k), tag, tf, (255, 70, 60, 255), (255, 255, 255, 255), int(7 * k))
                rot = rot.rotate(-4, resample=Image.BICUBIC)
                ta = min(1.0, u / 0.08) * min(1.0, (b - t) / 0.2)
                if ta < 1: rot.putalpha(Image.fromarray((np.asarray(rot.getchannel("A")) * ta).astype(np.uint8)))
                lay.alpha_composite(rot, (0, int(ccy + 70 * k)))
    a = np.asarray(lay, dtype=np.float32) / 255.0
    return a[..., :3], a[..., 3:4] * al

if __name__ == "__main__":
    # preview: python whatif_hud.py EPISODE_DIR t1 t2 ...  (EPISODE_DIR/hud_ep.py defines EP)
    import sys, importlib.util
    spec = importlib.util.spec_from_file_location("ep", os.path.join(sys.argv[1], "hud_ep.py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    W, H = 540, 960
    bg = np.zeros((H, W, 3), np.float32); bg[:] = (0.25, 0.55, 0.75)
    tiles = []
    for ts in sys.argv[2:]:
        t = float(ts)
        L = hud(t, m.EP, W, H)
        img = bg if L is None else bg * (1 - L[1]) + L[0] * L[1]
        im = Image.fromarray((img * 255).astype(np.uint8)); ImageDraw.Draw(im).text((10, H - 30), f"t={t}", fill=(255, 255, 255))
        tiles.append(im)
    sheet = Image.new("RGB", (W * len(tiles), H))
    for i, im in enumerate(tiles): sheet.paste(im, (i * W, 0))
    out = os.path.join(sys.argv[1], "hud_preview.png"); sheet.save(out); print(out)
