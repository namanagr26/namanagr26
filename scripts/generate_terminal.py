#!/usr/bin/env python3
"""
Generates terminal.svg: an animated terminal that types out what Naman works on.

Static content, so it is run by hand (not by the daily stats action):
    python3 scripts/generate_terminal.py

Edit SESSION below to change what the terminal shows. Every line must fit in
about 96 characters. The font is a subset of JetBrains Mono (ASCII plus a few
symbols such as the em dash, bullet and arrow), so stick to those characters.

Animation uses SMIL. Every element's resting state is fully visible, so a
viewer that ignores animation still shows the finished terminal.
"""
import base64
import os
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "terminal.svg")

BG, BAR, BORDER = "#0d1117", "#161b22", "#30363d"
FG, DIM = "#e6edf3", "#8b949e"
BLUE, GREEN, RED, YELLOW, PURPLE = "#58a6ff", "#3fb950", "#f85149", "#d29922", "#bc8cff"

FS, CW, LH = 14, 8.4, 22          # font size, char advance (0.6em), line height
PAD_X, TOP = 22, 58               # left padding, y of first baseline
W = 900
TYPE_SPEED = 0.042                # seconds per typed character
OUT_GAP, OUT_STEP, CMD_GAP = 0.25, 0.11, 0.55

PROMPT = [("naman@kali", GREEN), (":", FG), ("~", BLUE), ("$ ", FG)]

# Each entry: ("cmd", "text")  or  ("out", [(text, colour), ...])
SESSION = [
    ("cmd", "whoami"),
    ("out", [("naman agarwal", FG), (" — ai/ml engineer • cybersecurity intern @ skillorbit • tinsukia, assam", DIM)]),
    ("cmd", "nmap -sV --top-domains naman"),
    ("out", [("PORT      STATE  SERVICE        VERSION", DIM)]),
    ("out", [("22/tcp    ", FG), ("open   ", GREEN), ("cybersecurity  ", BLUE), ("burp suite, nmap, shodan, scapy, kali linux, owasp top 10", FG)]),
    ("out", [("80/tcp    ", FG), ("open   ", GREEN), ("ai-ml          ", BLUE), ("tensorflow, scikit-learn, transformers, llm integration", FG)]),
    ("out", [("443/tcp   ", FG), ("open   ", GREEN), ("data           ", BLUE), ("sql, pandas, tableau, power bi, streamlit", FG)]),
    ("out", [("8080/tcp  ", FG), ("open   ", GREEN), ("shipping       ", BLUE), ("3 live dashboards, netlify, gradio, spring boot", FG)]),
    ("cmd", "python detector.py --watch"),
    ("out", [("[ok] ", GREEN), ("no new suspicious activity (11394 packets checked)", DIM)]),
    ("out", [("[ALERT][HIGH] ", RED), ("Port Scan Behaviour", FG), ("  src=127.0.0.1  37 different ports probed within 10s", DIM)]),
    ("out", [("[ALERT][HIGH] ", RED), ("Repeated Access Attempts", FG), ("  src=127.0.0.1  50 connection attempts to port 22", DIM)]),
    ("cmd", "cat audio-captioning/results.txt"),
    ("out", [("BLEU-4 ", DIM), ("0.35", YELLOW), ("  •  METEOR ", DIM), ("0.40", YELLOW), ("  •  ROUGE-L F1 ", DIM), ("0.38", YELLOW), ("   (1,045 test clips, clotho v2)", DIM)]),
    ("cmd", "cat now.txt"),
    ("out", [("-> ", PURPLE), ("building where ai meets security: models, detection tooling, live dashboards", FG)]),
    ("prompt", ""),
]


def font_b64(name):
    with open(os.path.join(HERE, "fonts", name), "rb") as fh:
        return base64.b64encode(fh.read()).decode()


def tspans(parts):
    return "".join(f'<tspan fill="{c}">{escape(t)}</tspan>' for t, c in parts)


def reveal(t, total):
    """Hidden until time t, then visible. Resting value is visible."""
    f = max(min(t / total, 0.9999), 0.0)
    # discrete mode: each value holds from its keyTime until the next one
    return (f'<animate attributeName="opacity" values="0;1" keyTimes="0;{f:.4f}" '
            f'dur="{total:.2f}s" fill="freeze" calcMode="discrete"/>') if t > 0 else ""


def build():
    # 1) schedule
    t, events = 0.4, []
    for i, (kind, payload) in enumerate(SESSION):
        if kind == "cmd":
            dur = max(len(payload) * TYPE_SPEED, 0.3)
            events.append((kind, payload, t, dur))
            t += dur + OUT_GAP
        elif kind == "out":
            events.append((kind, payload, t, 0))
            t += OUT_STEP
            if i + 1 < len(SESSION) and SESSION[i + 1][0] != "out":
                t += CMD_GAP          # pause after a block of output
        else:
            events.append((kind, payload, t, 0))
    total = t + 0.2

    lines = len(SESSION)
    H = TOP + (lines - 1) * LH + 26
    prompt_w = sum(len(x) for x, _ in PROMPT) * CW

    body, defs = [], []
    for i, (kind, payload, start, dur) in enumerate(events):
        y = TOP + i * LH
        if kind in ("cmd", "prompt"):
            body.append(f'<g opacity="1">{reveal(start, total)}'
                        f'<text x="{PAD_X}" y="{y}" xml:space="preserve">{tspans(PROMPT)}</text></g>')
        if kind == "cmd":
            cx = PAD_X + prompt_w
            full = len(payload) * CW + 2
            f0, f1 = start / total, min((start + dur) / total, 0.9999)
            defs.append(f'<clipPath id="c{i}"><rect x="{cx:.1f}" y="{y - FS}" height="{LH}" width="{full:.1f}">'
                        f'<animate attributeName="width" values="0;0;{full:.1f};{full:.1f}" '
                        f'keyTimes="0;{f0:.4f};{f1:.4f};1" dur="{total:.2f}s" fill="freeze"/></rect></clipPath>')
            body.append(f'<text x="{cx:.1f}" y="{y}" fill="{FG}" clip-path="url(#c{i})" '
                        f'xml:space="preserve">{escape(payload)}</text>')
        elif kind == "out":
            body.append(f'<g opacity="1">{reveal(start, total)}'
                        f'<text x="{PAD_X}" y="{y}" xml:space="preserve">{tspans(payload)}</text></g>')
        elif kind == "prompt":
            cx = PAD_X + prompt_w
            body.append(f'<g opacity="1">{reveal(start, total)}'
                        f'<rect x="{cx:.1f}" y="{y - FS + 2}" width="{CW:.1f}" height="{FS + 2}" fill="{FG}">'
                        f'<animate attributeName="opacity" values="1;0" keyTimes="0;0.5" calcMode="discrete" '
                        f'dur="1.1s" repeatCount="indefinite"/></rect></g>')

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="t d">
<title id="t">naman@kali terminal</title>
<desc id="d">Animated terminal: whoami, an nmap-style scan of Naman's domains (cybersecurity, AI/ML, data, shipping), his intrusion detector catching a port scan and SSH brute force, and his audio-captioning model scores.</desc>
<defs>
<style>
@font-face{{font-family:"JBM";src:url(data:font/woff2;base64,{font_b64("text-regular.woff2")}) format("woff2");font-weight:400;}}
@font-face{{font-family:"JBM";src:url(data:font/woff2;base64,{font_b64("text-bold.woff2")}) format("woff2");font-weight:700;}}
text{{font-family:"JBM",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:{FS}px;}}
</style>
{"".join(defs)}
</defs>
<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="10" fill="{BG}" stroke="{BORDER}"/>
<path d="M0.5 32 V10.5 a10 10 0 0 1 10 -10 H{W - 10.5} a10 10 0 0 1 10 10 V32 Z" fill="{BAR}"/>
<line x1="0.5" y1="32" x2="{W - 0.5}" y2="32" stroke="{BORDER}"/>
<circle cx="20" cy="16" r="6" fill="#ff5f56"/><circle cx="40" cy="16" r="6" fill="#ffbd2e"/><circle cx="60" cy="16" r="6" fill="#27c93f"/>
<text x="{W / 2}" y="21" fill="{DIM}" text-anchor="middle" style="font-size:12px">naman@kali: ~</text>
{chr(10).join(body)}
</svg>
'''
    with open(OUT, "w") as fh:
        fh.write(svg)
    longest = max(len("".join(x for x, _ in p)) if k == "out" else len(p) + 13 for k, p in SESSION if k != "prompt")
    print(f"wrote terminal.svg  {W}x{H}  animation {total:.1f}s  longest line {longest} chars")


if __name__ == "__main__":
    build()
