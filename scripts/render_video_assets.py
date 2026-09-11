"""Render title cards (and a step-7 terminal clip) for the per-step demo
videos, reusing the exact fonts/colors from the React dashboard so the
whole video set feels like one product, not seven disconnected scripts."""

import os

from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 720
INK_950 = (11, 24, 38)
INK_900 = (15, 34, 51)
LINE = (39, 68, 96)
TEAL = (0, 194, 178)
AMBER = (232, 162, 61)
TEXT_HI = (234, 242, 246)
TEXT_MID = (169, 193, 209)
TEXT_DIM = (91, 112, 131)

FONT_DIR = "/tmp/fonts"
F_BOLD = os.path.join(FONT_DIR, "SpaceGrotesk-Bold.ttf")
F_SEMI = os.path.join(FONT_DIR, "SpaceGrotesk-SemiBold.ttf")
F_MONO = os.path.join(FONT_DIR, "IBMPlexMono-Regular.ttf")
F_SANS = os.path.join(FONT_DIR, "IBMPlexSans-Regular.ttf")


def title_card(step_num: int, title: str, summary: str, out_path: str):
    img = Image.new("RGB", (W, H), INK_950)
    d = ImageDraw.Draw(img)

    f_label = ImageFont.truetype(F_MONO, 22)
    f_title = ImageFont.truetype(F_BOLD, 56)
    f_summary = ImageFont.truetype(F_SANS, 24)
    f_wordmark = ImageFont.truetype(F_SEMI, 22)

    d.text((70, 56), "Slick Trace / OilTrace", font=f_wordmark, fill=TEXT_DIM)
    d.line([(70, 96), (W - 70, 96)], fill=LINE, width=1)

    d.text((70, 280), f"STEP {step_num}", font=f_label, fill=TEAL)
    d.text((70, 320), title, font=f_title, fill=TEXT_HI)

    # wrap summary to ~70 chars
    import textwrap
    lines = textwrap.wrap(summary, width=70)
    y = 410
    for line in lines:
        d.text((70, y), line, font=f_summary, fill=TEXT_MID)
        y += 34

    img.save(out_path)


def pad_to_canvas(src_path: str, out_path: str, bg=INK_950):
    """Letterbox an existing artifact image onto a WxH navy canvas so every
    clip in the video set shares the same resolution."""
    src = Image.open(src_path).convert("RGB")
    scale = min(W / src.width, H / src.height)
    new_size = (int(src.width * scale), int(src.height * scale))
    resized = src.resize(new_size, Image.LANCZOS)
    canvas = Image.new("RGB", (W, H), bg)
    canvas.paste(resized, ((W - new_size[0]) // 2, (H - new_size[1]) // 2))
    canvas.save(out_path)


def terminal_clip_frame(lines: list[str], out_path: str):
    """Same terminal aesthetic as scripts/visualize_nlp.py, for step 7's
    startup-check + smoke-test output."""
    img = Image.new("RGB", (W, H), INK_950)
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(F_MONO, 16)
    y = 40
    for line in lines:
        color = TEAL if line.startswith("===") else \
                (63, 185, 80) if "[ok]" in line or "PASS" in line else \
                AMBER if "[FAIL]" in line else \
                TEXT_HI
        d.text((40, y), line, font=f, fill=color)
        y += 24
        if y > H - 40:
            break
    img.save(out_path)


STEP_CARDS = [
    (1, "Incident schema + synthetic case",
     "A join-contract schema, and a synthetic scene with one true release and four decoy vessels."),
    (2, "Detection",
     "Classical baseline: 0.68 IoU on real slicks, 0% false positives on look-alikes and clean water."),
    (3, "Historical AIS mapping",
     "Backward hindcast envelope narrows five vessels to two or three genuine candidates."),
    (4, "Forward-replay attribution",
     "Beats the naive proximity baseline on the exact decoy trap it's designed to catch."),
    (5, "Ask Slick Trace",
     "Seven grounded query intents, fully cited, with honest refusals on what it can't answer."),
    (6, "FastAPI + React app",
     "A real working dashboard, verified with an actual headless browser session."),
    (7, "Docker packaging",
     "Startup checks and a release-acceptance smoke test, run and passing against the live app."),
]

if __name__ == "__main__":
    os.makedirs("videos/frames", exist_ok=True)
    for num, title, summary in STEP_CARDS:
        title_card(num, title, summary, f"videos/frames/title_{num}.png")
    print("Title cards rendered.")
