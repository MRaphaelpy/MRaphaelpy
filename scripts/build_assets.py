import base64
import io
import math
import re
import urllib.request
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets"
CACHE = Path(__file__).resolve().parent / ".cache"
W = 1280

FONT_URL = ("https://github.com/google/fonts/raw/main/ofl/robotoflex/"
            "RobotoFlex%5BGRAD,XOPQ,XTRA,YOPQ,YTAS,YTDE,YTFI,YTLC,YTUC,opsz,slnt,wdth,wght%5D.ttf")
SIMPLE_ICONS = "https://cdn.jsdelivr.net/npm/simple-icons@15.0.0/icons/{}.svg"
SKILL_ICONS = "https://skillicons.dev/icons?i={}&theme={}"

THEMES = {
    "dark": dict(
        surface="#1D1B20", surface_hi="#2B2930", text="#E6E0E9", text_var="#CAC4D0",
        primary="#D0BCFF", on_primary="#381E72", pc="#4F378B", on_pc="#EADDFF",
        sc="#4A4458", on_sc="#E8DEF8", tertiary="#EFB8C8", tc="#633B48", on_tc="#FFD8E4",
        lime="#C6F36D", on_lime="#1E3300", outline="#49454F",
    ),
    "light": dict(
        surface="#F7F2FA", surface_hi="#ECE6F0", text="#1D1B20", text_var="#49454F",
        primary="#6750A4", on_primary="#FFFFFF", pc="#EADDFF", on_pc="#21005D",
        sc="#E8DEF8", on_sc="#1D192B", tertiary="#7D5260", tc="#FFD8E4", on_tc="#31111D",
        lime="#C6F36D", on_lime="#1E3300", outline="#CAC4D0",
    ),
}

SPRING = "cubic-bezier(.34,1.56,.64,1)"
EMPHASIZED = "0.2 0 0 1"


def fetch(url, name):
    CACHE.mkdir(exist_ok=True)
    path = CACHE / name
    if not path.exists():
        req = urllib.request.Request(url, headers={"User-Agent": "readme-builder"})
        path.write_bytes(urllib.request.urlopen(req).read())
    return path.read_bytes()


class Font:
    def __init__(self, family, axes):
        self.family = family
        base = TTFont(io.BytesIO(fetch(FONT_URL, "RobotoFlex.ttf")))
        pins = {a.axisTag: a.defaultValue for a in base["fvar"].axes}
        pins.update(axes)
        static = instancer.instantiateVariableFont(base, pins)
        buf = io.BytesIO()
        static.save(buf)
        self.data = buf.getvalue()
        self.upm = static["head"].unitsPerEm
        self.cmap = static.getBestCmap()
        self.hmtx = static["hmtx"]

    def width(self, text, size, spacing=0.0):
        adv = sum(self.hmtx[self.cmap.get(ord(c), ".notdef")][0] for c in text)
        return adv * size / self.upm + spacing * max(len(text) - 1, 0)

    def face(self, chars):
        font = TTFont(io.BytesIO(self.data))
        opts = subset.Options()
        opts.flavor = "woff2"
        opts.layout_features = ["kern", "liga"]
        sub = subset.Subsetter(opts)
        sub.populate(text="".join(sorted(set(chars))) + " ")
        sub.subset(font)
        buf = io.BytesIO()
        font.flavor = "woff2"
        font.save(buf)
        b64 = base64.b64encode(buf.getvalue()).decode()
        return f"@font-face{{font-family:'{self.family}';src:url(data:font/woff2;base64,{b64}) format('woff2')}}"


DISPLAY = Font("Display", {"wght": 860, "wdth": 120, "opsz": 144})
LABEL = Font("Label", {"wght": 650, "wdth": 108, "opsz": 24})
BODY = Font("Body", {"wght": 430, "wdth": 100, "opsz": 32})
FONTS = {"D": DISPLAY, "L": LABEL, "B": BODY}


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


class Svg:

    def __init__(self, w, h, title):
        self.w, self.h, self.title = w, h, title
        self.parts, self.css, self.chars = [], [], {k: set() for k in FONTS}

    def add(self, s):
        self.parts.append(s)

    def text(self, x, y, s, font="D", size=40, fill="#000", anchor="start", spacing=0, extra=""):
        self.chars[font] |= set(s)
        ls = f' letter-spacing="{spacing}"' if spacing else ""
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" font-family="{FONTS[font].family}" font-size="{size}" '
                 f'fill="{fill}" text-anchor="{anchor}"{ls} {extra}>{esc(s)}</text>')

    def render(self):
        faces = "".join(FONTS[k].face(c) for k, c in self.chars.items() if c)
        css = faces + "".join(self.css) + \
            "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
                f'viewBox="0 0 {self.w} {self.h}" role="img" aria-label="{esc(self.title)}">'
                f"<title>{esc(self.title)}</title><style>{css}</style>{''.join(self.parts)}</svg>")


def wrap(text, font, size, maxw):
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if font.width(trial, size) > maxw and cur:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    return lines + [cur]


N = 120


def _radii(kind):
    th = [2 * math.pi * i / N for i in range(N)]
    if kind == "circle":
        r = [1.0] * N
    elif kind.startswith("cookie"):
        n = int(kind[6:])
        r = [1 + 0.075 * math.cos(n * t) for t in th]
    elif kind == "sunny":
        r = [1 + 0.11 * math.cos(8 * t) for t in th]
    elif kind == "flower":
        r = [0.78 + 0.22 * abs(math.cos(4 * t)) ** 0.7 for t in th]
    elif kind == "clover":
        r = [0.62 + 0.38 * abs(math.cos(2 * t)) ** 0.6 for t in th]
    elif kind == "burst":
        r = [1 + 0.16 * math.cos(12 * t) for t in th]
    elif kind == "squircle":
        p = 4.5
        r = [(abs(math.cos(t)) ** p + abs(math.sin(t)) ** p) ** (-1 / p) for t in th]
    elif kind == "diamond":
        p = 1.6
        r = [(abs(math.cos(t)) ** p + abs(math.sin(t)) ** p) ** (-1 / p) for t in th]
    elif kind == "pentagon":
        r = [1 + 0.12 * math.cos(5 * t) for t in th]
    else:
        raise ValueError(kind)
    m = max(r)
    return th, [v / m for v in r]


def shape(kind, cx, cy, R, rot=0.0):
    th, r = _radii(kind)
    a = math.radians(rot)
    pts = [(cx + R * v * math.cos(t + a), cy + R * v * math.sin(t + a)) for t, v in zip(th, r)]
    d = f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"
    for i in range(N):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[(i + 1) % N], pts[(i + 2) % N]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d += f"C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}"
    return d + "Z"


def morph(kinds, cx, cy, R, fill, dur=12, rot=0.0, cls=""):
    paths = [shape(k, cx, cy, R, rot) for k in kinds + kinds[:1]]
    n = len(paths) - 1
    times = ";".join(f"{i / n:.3f}" for i in range(n + 1))
    splines = ";".join([EMPHASIZED] * n)
    c = f' class="{cls}"' if cls else ""
    return (f'<g{c}><path d="{paths[0]}" fill="{fill}"><animate attributeName="d" dur="{dur}s" '
            f'repeatCount="indefinite" values="{";".join(paths)}" keyTimes="{times}" '
            f'calcMode="spline" keySplines="{splines}"/></path></g>')


ANIM_CSS = (
    ".spin{transform-box:fill-box;transform-origin:center;animation:spin 28s linear infinite}"
    ".spin-r{transform-box:fill-box;transform-origin:center;animation:spin 18s linear infinite reverse}"
    "@keyframes spin{to{transform:rotate(360deg)}}"
    f".bob{{transform-box:fill-box;animation:bob 3.2s {SPRING} infinite alternate}}"
    "@keyframes bob{from{transform:translateY(-10px)}to{transform:translateY(10px)}}"
    f".pop{{transform-box:fill-box;transform-origin:center;animation:pop 4s {SPRING} infinite}}"
    "@keyframes pop{0%,100%{transform:scale(1)}50%{transform:scale(.82) rotate(45deg)}}"
)


def pill(svg, x, y, label, bg, fg, size=22, font="L", pad=22, h=None, spacing=1.2):
    h = h or size * 2.1
    w = FONTS[font].width(label, size, spacing) + pad * 2
    svg.add(f'<rect x="{x}" y="{y}" width="{w:.1f}" height="{h:.1f}" rx="{h / 2:.1f}" fill="{bg}"/>')
    svg.text(x + w / 2, y + h / 2 + size * 0.36, label, font, size, fg, "middle", spacing)
    return w


def hero(t):
    s = Svg(W, 540, "Marcos Rafael — Desenvolvedor Full Stack, Mobile e apaixonado por Linux")
    s.css.append(ANIM_CSS)
    s.add(f'<clipPath id="hc"><rect width="{W}" height="540" rx="56"/></clipPath>')
    s.add(f'<rect width="{W}" height="540" rx="56" fill="{t["pc"]}"/>')
    s.add(f'<g clip-path="url(#hc)" opacity=".55">{morph(["burst", "flower"], 1240, 560, 260, t["sc"], 16, cls="spin")}</g>')

    s.add(morph(["cookie9", "flower", "squircle", "sunny"], 960, 250, 170, t["primary"], 14, cls="spin"))
    s.text(960, 290, "MR", "D", 118, t["on_primary"], "middle", -2)
    s.add(morph(["clover", "pentagon"], 1170, 92, 50, t["tertiary"], 9, cls="spin-r"))
    s.add(f'<g class="bob"><rect x="752" y="410" width="168" height="64" rx="32" fill="{t["lime"]}" '
          f'transform="rotate(-18 836 442)"/></g>')
    s.add(f'<g class="pop">{morph(["diamond", "circle"], 1180, 440, 34, t["tc"], 7)}</g>')
    s.add(f'<circle cx="790" cy="96" r="18" fill="{t["on_pc"]}" opacity=".9" class="bob"/>')

    pill(s, 72, 64, "OLÁ, MUNDO! EU SOU", t["primary"], t["on_primary"], 20, spacing=2)
    s.text(66, 244, "Marcos", "D", 136, t["on_pc"], spacing=-3)
    s.text(66, 372, "Rafael", "D", 136, t["primary"], spacing=-3)

    words = ["apps mobile", "APIs robustas", "interfaces lindas", "automações"]
    size, lh = 34, 60
    prefix = "Eu crio"
    px = 72
    s.text(px, 466, prefix, "B", size, t["on_pc"])
    bx = px + BODY.width(prefix + " ", size) + 4
    bw = max(LABEL.width(w, size) for w in words) + 48
    by = 466 - size * 0.36 - lh / 2
    s.add(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{lh}" rx="{lh / 2}" fill="{t["lime"]}"/>')
    s.add(f'<clipPath id="wc"><rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{lh}" rx="{lh / 2}"/></clipPath>')
    steps = len(words)
    frames = []
    for i in range(steps):
        a, b = i / steps * 100, (i + 1) / steps * 100
        frames.append(f"{a:.2f}%,{b - 7:.2f}%{{transform:translateY({-i * lh}px);animation-timing-function:{SPRING}}}")
    frames.append(f"100%{{transform:translateY({-steps * lh}px)}}")
    s.css.append(".words{animation:words 11s infinite}@keyframes words{" + "".join(frames) + "}")
    s.add('<g clip-path="url(#wc)"><g class="words">')
    for i, w in enumerate(words + words[:1]):
        s.text(bx + bw / 2, 466 + i * lh, w, "L", size, t["on_lime"], "middle")
    s.add("</g></g>")
    return s


def title(t, label, num, kinds):
    s = Svg(W, 120, label)
    s.css.append(ANIM_CSS)
    s.add(f'<g class="spin">{morph(kinds, 44, 60, 36, t["primary"], 8)}</g>')
    s.text(104, 78, label, "D", 52, t["text"], spacing=-1)
    tw = 104 + DISPLAY.width(label, 52, -1) + 28
    s.add(f'<rect x="{tw:.0f}" y="58" width="{W - tw - 120:.0f}" height="4" rx="2" fill="{t["outline"]}"/>')
    pill(s, W - 96, 38, num, t["sc"], t["on_sc"], 20, pad=24, h=44)
    return s


def tile(s, x, y, w, h, fill, r=40):
    s.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}"/>')


def about(t):
    s = Svg(W, 640, "Sobre mim: estudante de Ciência da Computação na UNIVASF, dev Full Stack do Ceará")
    s.css.append(ANIM_CSS)
    g = 20
    tile(s, 0, 0, 780, 330, t["surface_hi"])
    pill(s, 40, 40, "QUEM SOU EU", t["primary"], t["on_primary"], 18, spacing=2)
    txt = ("Estudante de Ciência da Computação e desenvolvedor Full Stack. "
           "Curto integrar APIs, automatizar sistemas e resolver problemas com código limpo e elegante.")
    for i, line in enumerate(wrap(txt, BODY, 32, 700)):
        s.text(40, 146 + i * 44, line, "B", 32, t["text"])
    tile(s, 780 + g, 0, W - 780 - g, 330, t["tc"])
    s.add(f'<g class="spin">{morph(["sunny", "burst", "cookie12"], 1150, 110, 78, t["tertiary"], 10)}</g>')
    s.text(840, 228, "Ceará", "D", 84, t["on_tc"], spacing=-2)
    s.text(844, 278, "BRASIL · NORDESTE", "L", 20, t["on_tc"], spacing=3)

    y2, h2 = 330 + g, 640 - 330 - g
    w = (W - 2 * g) / 3
    x = 0
    tile(s, x, y2, w, h2, t["lime"])
    s.add(f'<path d="M{x + w - 150},{y2 + 150} v-50 a50,50 0 0 1 100,0 v50 z" fill="{t["on_lime"]}" opacity=".9" class="bob"/>')
    s.text(x + 40, y2 + 70, "FORMAÇÃO", "L", 18, t["on_lime"], spacing=3)
    s.text(x + 38, y2 + 200, "UNIVASF", "D", 60, t["on_lime"], spacing=-1)
    s.text(x + 40, y2 + 244, "Ciência da Computação", "B", 26, t["on_lime"])
    x = w + g
    tile(s, x, y2, w, h2, t["pc"])
    s.add(f'<g class="spin-r">{morph(["clover", "flower"], x + w - 90, y2 + 90, 50, t["primary"], 8)}</g>')
    s.text(x + 40, y2 + 70, "SISTEMA", "L", 18, t["on_pc"], spacing=3)
    s.text(x + 38, y2 + 200, "Linux", "D", 60, t["on_pc"], spacing=-1)
    s.add(f'<rect x="{x + 40}" y="{y2 + 222}" width="{w - 80:.0f}" height="44" rx="22" fill="{t["surface"]}" opacity=".85"/>')
    s.chars["L"] |= set("$ sudo pacman -Syu")
    s.add(f'<text x="{x + 62}" y="{y2 + 251}" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" '
          f'font-size="20" fill="{t["text"]}">$ sudo pacman -Syu</text>')
    x = 2 * (w + g)
    tile(s, x, y2, w, h2, t["sc"])
    s.text(x + 40, y2 + 70, "NOS FONES", "L", 18, t["on_sc"], spacing=3)
    s.text(x + 38, y2 + 200, "Música", "D", 60, t["on_sc"], spacing=-1)
    s.text(x + 40, y2 + 244, "trilha sonora do código", "B", 26, t["on_sc"])
    bars = [0.9, 0.45, 0.75, 0.35, 0.6]
    s.css.append(f".eq{{transform-box:fill-box;transform-origin:50% 100%;animation:eq 1.1s {SPRING} infinite alternate}}"
                 "@keyframes eq{from{transform:scaleY(.25)}to{transform:scaleY(1)}}")
    for i, b in enumerate(bars):
        bh = 90 * b + 20
        s.add(f'<rect class="eq" style="animation-delay:-{i * 0.37:.2f}s" x="{x + w - 200 + i * 30:.0f}" '
              f'y="{y2 + 140 - bh:.0f}" width="18" height="{bh:.0f}" rx="9" fill="{t["primary"]}"/>')
    return s


STACK = [
    ("FRONT-END", ["react", "ts", "js", "html", "css", "bootstrap"]),
    ("BACK-END", ["spring", "java", "nodejs", "php", "laravel"]),
    ("MOBILE", ["flutter", "dart", "kotlin", "androidstudio"]),
    ("BANCOS DE DADOS", ["mysql", "postgres", "sqlite"]),
    ("FERRAMENTAS", ["git", "docker", "vscode", "figma", "postman"]),
    ("SISTEMAS", ["linux", "arch", "windows"]),
]


def icon_uri(name, theme):
    raw = fetch(SKILL_ICONS.format(name, theme), f"skill-{name}-{theme}.svg")
    return "data:image/svg+xml;base64," + base64.b64encode(raw).decode()


def stack(t, theme):
    g, th, isz, ig = 20, 196, 64, 14
    rows = [[0, 1], [2, 3, 4], [5, None]]
    s = Svg(W, len(rows) * th + (len(rows) - 1) * g, "Tecnologias: " +
            ", ".join(n for _, icons in STACK for n in icons))
    s.css.append(ANIM_CSS)
    fills = [("pc", "on_pc"), ("tc", "on_tc"), ("sc", "on_sc"), ("lime", "on_lime"),
             ("surface_hi", "text"), ("pc", "on_pc"), ("primary", "on_primary")]
    k = 0
    for r, row in enumerate(rows):
        y = r * (th + g)
        need = [len(STACK[i][1]) * (isz + ig) - ig + 80 if i is not None else 0 for i in row]
        spare = W - g * (len(row) - 1) - sum(need)
        extra = 0 if None in row else spare / len(row)
        x = 0
        for i, n in zip(row, need):
            w = (n or 0) + extra
            if i is None:
                w = W - x
                bg, fg = fills[6]
                tile(s, x, y, w, th, t[bg])
                s.add(f'<g class="spin">{morph(["cookie9", "squircle"], x + w - 100, y + th / 2, 62, t["on_primary"], 10)}</g>')
                s.text(x + 44, y + 92, "Sempre aprendendo", "D", 46, t[fg], spacing=-1)
                s.text(x + 46, y + 136, "e evoluindo com novas tecnologias", "B", 26, t[fg])
                break
            bg, fg = fills[k % 5]
            k += 1
            tile(s, x, y, w, th, t[bg])
            label, icons = STACK[i]
            s.text(x + 40, y + 58, label, "L", 18, t[fg], spacing=3)
            for j, ic in enumerate(icons):
                s.add(f'<image x="{x + 40 + j * (isz + ig):.1f}" y="{y + 90}" width="{isz}" height="{isz}" '
                      f'href="{icon_uri(ic, theme)}"/>')
            x += w + g
    return s


def footer(t):
    lines = wrap("O código é como poesia — deve ser escrito para humanos lerem, "
                 "e apenas incidentalmente para máquinas executarem.", DISPLAY, 40, 900)
    H = 100 + len(lines) * 52 + 30 + 42 + 56
    s = Svg(W, H, "O código é como poesia — deve ser escrito para humanos lerem, e apenas incidentalmente para máquinas executarem.")
    s.css.append(ANIM_CSS)
    tile(s, 0, 0, W, H, t["surface_hi"], 56)
    s.add(f'<g class="spin">{morph(["flower", "cookie12", "clover"], 1130, H / 2, 110, t["pc"], 12)}</g>')
    s.text(1130, H / 2 + 52, "“", "D", 170, t["primary"], "middle")
    for i, line in enumerate(lines):
        s.text(60, 100 + i * 52, line, "D", 40, t["text"], spacing=-0.5)
    y = 100 + len(lines) * 52 + 30
    w = pill(s, 60, y, "FEITO COM CAFÉ", t["lime"], t["on_lime"], 18, spacing=2)
    pill(s, 60 + w + 12, y, 'git commit -m "agora vai"', t["sc"], t["on_sc"], 18, spacing=0.5)
    return s


BUTTONS = [
    ("linkedin", "LinkedIn", "#0A66C2"),
    ("gmail", "E-mail", "#C5221F"),
    ("whatsapp", "WhatsApp", "#1DA851"),
    ("telegram", "Telegram", "#229ED9"),
    ("discord", "Discord", "#5865F2"),
    ("instagram", "Instagram", "#D62976"),
    ("x", "X", "#000000"),
]


def button(slug, label, color):
    size, h, pad, isz = 22, 64, 28, 26
    tw = LABEL.width(label, size, 0.5)
    w = pad + isz + 12 + tw + pad
    s = Svg(int(w), h, label)
    s.css.append(f".b{{transform-origin:center;transform-box:fill-box;transition:transform .3s {SPRING}}}")
    s.add(f'<rect class="b" width="{w:.0f}" height="{h}" rx="{h / 2}" fill="{color}"/>')
    if slug == "linkedin":
        s.add(f'<rect x="{pad}" y="{(h - isz) / 2}" width="{isz}" height="{isz}" rx="6" fill="#fff"/>')
        s.text(pad + isz / 2, h / 2 + 7.5, "in", "D", 19, color, "middle")
    else:
        d = re.search(r'<path d="([^"]+)"', fetch(SIMPLE_ICONS.format(slug), f"si-{slug}.svg").decode()).group(1)
        s.add(f'<path d="{d}" fill="#fff" transform="translate({pad},{(h - isz) / 2}) scale({isz / 24})"/>')
    s.text(pad + isz + 12, h / 2 + size * 0.36, label, "L", size, "#FFFFFF", spacing=0.5)
    return s


SECTIONS = [
    ("sobre", "Sobre mim", ["cookie9", "flower"]),
    ("stack", "Arsenal", ["squircle", "clover"]),
    ("stats", "Números", ["burst", "pentagon"]),
    ("3d", "Contribuições", ["diamond", "cookie12"]),
    ("musica", "No repeat", ["flower", "sunny"]),
    ("contato", "Bora conversar?", ["clover", "circle"]),
]


def main():
    if OUT.is_file():
        OUT.unlink()
    OUT.mkdir(exist_ok=True)
    for theme, t in THEMES.items():
        pieces = {"hero": hero(t), "sobre": about(t), "stack": stack(t, theme), "footer": footer(t)}
        for i, (slug, label, kinds) in enumerate(SECTIONS, 1):
            pieces[f"title-{slug}"] = title(t, label, f"{i:02d}", kinds)
        for name, svg in pieces.items():
            (OUT / f"{name}-{theme}.svg").write_text(svg.render(), encoding="utf-8")
    for slug, label, color in BUTTONS:
        (OUT / f"btn-{slug}.svg").write_text(button(slug, label, color).render(), encoding="utf-8")
    for p in sorted(OUT.iterdir()):
        print(f"{p.stat().st_size / 1024:7.1f} KB  {p.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
