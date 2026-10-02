"""Generate the SmartSharing Studio starter catalogue: real, downloadable creator files.

    python -m seed.official_products          # build files + covers, upsert listings (idempotent)

Every product is made by this script (original work, no third-party assets), zipped, stored in backend/storage,
and listed under the official @smartsharing.studio account. Prices are in credits.
"""
import io
import json
import math
import random
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cairosvg  # noqa: E402
from docx import Document  # noqa: E402
from docx.shared import Pt  # noqa: E402
from openpyxl import Workbook  # noqa: E402
from openpyxl.styles import Alignment, Font, PatternFill  # noqa: E402
from openpyxl.worksheet.datavalidation import DataValidation  # noqa: E402
from PIL import Image, ImageDraw, ImageFilter, ImageFont  # noqa: E402

from app.db import ensure_indexes, ensure_platform_account, get_db  # noqa: E402
from app.services import storage  # noqa: E402
from app.services.market import create_asset  # noqa: E402
from app.services.users import create_user  # noqa: E402
from app.util import now_utc  # noqa: E402

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
LIME, INK, PAPER = "#d6ff7f", "#0b0e13", "#f4f5f7"
LICENSE_TXT = """SmartSharing Licence — {name}
Licence type: as purchased (see your receipt in SmartSharing → Library).

You may: use these files in unlimited personal and client/commercial projects (per your licence tier),
modify them, and publish the resulting work.
You may not: resell, redistribute, sublicense or share the source files, or include them in another
template/asset pack.

Made by SmartSharing Studio · https://smartsharing.in · hello@smartsharing.in
"""


def zip_bytes(files: dict[str, bytes | str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data.encode() if isinstance(data, str) else data)
    return buf.getvalue()


def png(svg: str, w: int | None = None) -> bytes:
    return cairosvg.svg2png(bytestring=svg.encode(), output_width=w)


# ------------------------------------------------------------------ 1. LUTs
def _clamp(x):
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def _lut(fn, title, n=33) -> str:
    lines = [f'TITLE "{title}"', f"LUT_3D_SIZE {n}", "DOMAIN_MIN 0.0 0.0 0.0", "DOMAIN_MAX 1.0 1.0 1.0"]
    for b in range(n):
        for g in range(n):
            for r in range(n):
                R, G, B = fn(r / (n - 1), g / (n - 1), b / (n - 1))
                lines.append(f"{_clamp(R):.6f} {_clamp(G):.6f} {_clamp(B):.6f}")
    return "\n".join(lines) + "\n"


def _s(x, k=1.0):  # soft contrast curve
    return 0.5 + (x - 0.5) * k - 0.35 * (k - 1) * (x - 0.5) ** 3 * 4


def _luma(r, g, b):
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _sat(r, g, b, s):
    y = _luma(r, g, b)
    return y + (r - y) * s, y + (g - y) * s, y + (b - y) * s


LUTS = {
    "Monsoon Teal": lambda r, g, b: (lambda y: _sat(_s(r, 1.1) - 0.04 * (1 - y), _s(g, 1.08) + 0.02, _s(b, 1.05) + 0.06 * (1 - y), 0.82))(_luma(r, g, b)),
    "Golden Hour Warm": lambda r, g, b: _sat(_s(r, 1.05) + 0.06, _s(g, 1.03) + 0.025, _s(b, 1.02) - 0.05, 1.08),
    "Teal & Orange": lambda r, g, b: (lambda y: _sat(r + 0.08 * y - 0.04 * (1 - y), g + 0.01, b - 0.07 * y + 0.08 * (1 - y), 1.1))(_luma(r, g, b)),
    "Bollywood Pop": lambda r, g, b: _sat(_s(r, 1.15), _s(g, 1.1), _s(b, 1.12), 1.3),
    "Faded Film": lambda r, g, b: _sat(0.06 + 0.88 * _s(r, 0.95) + 0.02, 0.06 + 0.88 * _s(g, 0.95), 0.08 + 0.86 * _s(b, 0.95), 0.85),
    "Clean Matte B&W": lambda r, g, b: (lambda y: (0.05 + 0.9 * _s(y, 1.1),) * 3)(_luma(r, g, b)),
    "Kerala Green": lambda r, g, b: _sat(_s(r, 1.04) - 0.02, _s(g, 1.06) + 0.04, _s(b, 1.03) - 0.01, 1.12),
    "Night Street Neon": lambda r, g, b: (lambda y: _sat(r + 0.05 * (1 - y), g - 0.03, b + 0.1 * (1 - y), 1.18))(_luma(r, g, b)),
    "Desert Dust": lambda r, g, b: _sat(_s(r, 1.02) + 0.05, _s(g, 1.0) + 0.02, _s(b, 0.98) - 0.03, 0.78),
    "Crisp Commercial": lambda r, g, b: _sat(_s(r, 1.12), _s(g, 1.12), _s(b, 1.12), 1.05),
}


def _gradient_sample(w=900, h=300) -> Image.Image:
    img = Image.new("RGB", (w, h))
    px = img.load()
    for x in range(w):
        for y in range(h):
            hue = x / w
            v = 1 - y / h
            r = _clamp(abs(hue * 6 - 3) - 1) * v + (1 - v) * 0.1
            g = _clamp(2 - abs(hue * 6 - 2)) * v + (1 - v) * 0.1
            b = _clamp(2 - abs(hue * 6 - 4)) * v + (1 - v) * 0.1
            px[x, y] = (int(r * 255), int(g * 255), int(b * 255))
    return img


def product_luts():
    files = {}
    base = _gradient_sample()
    tiles = []
    for name, fn in LUTS.items():
        files[f"SmartSharing-LUTs/{name.replace(' ', '_')}.cube"] = _lut(fn, name)
        im = base.copy()
        px = im.load()
        for x in range(im.width):
            for y in range(im.height):
                r, g, b = [c / 255 for c in px[x, y]]
                R, G, B = fn(r, g, b)
                px[x, y] = (int(_clamp(R) * 255), int(_clamp(G) * 255), int(_clamp(B) * 255))
        tiles.append((name, im.resize((300, 100))))
    prev = Image.new("RGB", (620, 60 + 115 * 5), INK)
    d = ImageDraw.Draw(prev)
    f = ImageFont.truetype(FONT, 14)
    for i, (n, t) in enumerate(tiles):
        x, y = 10 + (i % 2) * 305, 40 + (i // 2) * 115
        prev.paste(t, (x, y))
        d.text((x, y - 18), n, font=f, fill=PAPER)
    b = io.BytesIO()
    prev.save(b, "PNG")
    files["SmartSharing-LUTs/preview.png"] = b.getvalue()
    files["SmartSharing-LUTs/HOW-TO-USE.txt"] = ("10 × 33-point .cube LUTs (Rec.709 in → Rec.709 out).\n\n"
        "Premiere Pro: Lumetri Color → Creative → Look → Browse.\nDaVinci Resolve: Project Settings → Color Management → "
        "Open LUT Folder, drop files, Update Lists. Apply on a node.\nFinal Cut Pro: Effects → Custom LUT.\n"
        "CapCut / LumaFusion / Lightroom (profiles): import .cube.\n\nTip: apply after exposure/white balance correction, "
        "then lower node/clip opacity to taste (60–80% looks natural).\n")
    return files, tiles


# ------------------------------------------------------------------ 2. GST invoice workbook
def product_invoice():
    wb = Workbook()
    ws = wb.active
    ws.title = "Invoice"
    bold, big = Font(bold=True), Font(bold=True, size=18)
    ws.column_dimensions["A"].width = 6
    ws.column_dimensions["B"].width = 44
    for c in "CDEFG":
        ws.column_dimensions[c].width = 15
    ws["B1"], ws["B1"].font = "TAX INVOICE", big
    rows = [("B3", "Your name / studio"), ("B4", "Address, City, State, PIN"), ("B5", "GSTIN: 22AAAAA0000A1Z5"),
            ("B6", "PAN: AAAAA0000A"), ("E3", "Invoice #"), ("F3", "INV-2026-001"), ("E4", "Date"), ("F4", "=TODAY()"),
            ("E5", "Due date"), ("F5", "=F4+15"), ("B8", "BILL TO"), ("B9", "Client name"), ("B10", "Client address"),
            ("B11", "Client GSTIN"), ("E8", "Place of supply (state)"), ("E9", "Supplier state"), ("F9", "Maharashtra"),
            ("F8", "Maharashtra")]
    for ref, val in rows:
        ws[ref] = val
    ws["B8"].font = ws["B3"].font = bold
    ws["E10"], ws["F10"] = "Tax type", '=IF(F8=F9,"CGST+SGST","IGST")'
    ws["E11"], ws["F11"] = "GST rate %", 18
    hdr = ["#", "Description of service / deliverable", "SAC", "Qty", "Rate (₹)", "Amount (₹)"]
    fill = PatternFill("solid", fgColor="D6FF7F")
    for i, h in enumerate(hdr):
        c = ws.cell(row=13, column=1 + i, value=h)
        c.font, c.fill = bold, fill
    items = [("Instagram Reel — concept, shoot & edit", "998361", 2, 12000), ("YouTube thumbnail design", "998391", 4, 1500),
             ("Usage rights — 6 months paid media", "997331", 1, 8000)]
    for r in range(14, 26):
        ws.cell(row=r, column=1, value=r - 13)
        if r - 14 < len(items):
            dsc, sac, q, rate = items[r - 14]
            ws.cell(row=r, column=2, value=dsc)
            ws.cell(row=r, column=3, value=sac)
            ws.cell(row=r, column=4, value=q)
            ws.cell(row=r, column=5, value=rate)
        ws.cell(row=r, column=6, value=f'=IF(D{r}="","",D{r}*E{r})')
    lab = [("Subtotal", "=SUM(F14:F25)"), ("CGST", '=IF($F$10="CGST+SGST",F27*$F$11/200,0)'),
           ("SGST", '=IF($F$10="CGST+SGST",F27*$F$11/200,0)'), ("IGST", '=IF($F$10="IGST",F27*$F$11/100,0)'),
           ("TDS deducted by client (194J, 10%) — optional", 0), ("TOTAL PAYABLE", "=F27+F28+F29+F30-F31")]
    for i, (l, f) in enumerate(lab):
        ws.cell(row=27 + i, column=5, value=l).font = bold
        ws.cell(row=27 + i, column=6, value=f)
    for r in range(14, 33):
        ws.cell(row=r, column=6).number_format = "₹#,##0.00"
        ws.cell(row=r, column=5).number_format = "#,##0"
    ws["F32"].font = Font(bold=True, size=13)
    ws["B35"] = "Bank: ______  A/C: ______  IFSC: ______   UPI: yourname@bank"
    ws["B36"] = "Payment terms: 15 days. Late payments attract interest under MSMED Act, 2006 (if registered)."
    ws["B38"] = "This is a template. Confirm GST registration, SAC codes and TDS treatment with your CA."
    ws["B38"].font = Font(italic=True, size=9)
    dv = DataValidation(type="list", formula1='"0,5,12,18,28"', allow_blank=False)
    ws.add_data_validation(dv)
    dv.add("F11")
    lg = wb.create_sheet("Payment tracker")
    cols = ["Invoice #", "Client", "Issued", "Due", "Amount (₹)", "Status", "Paid on", "Days late"]
    for i, h in enumerate(cols):
        c = lg.cell(row=1, column=1 + i, value=h)
        c.font, c.fill = bold, fill
        lg.column_dimensions[chr(65 + i)].width = 16
    for r in range(2, 202):
        lg.cell(row=r, column=8, value=f'=IF(AND(F{r}="Paid",G{r}<>""),MAX(0,G{r}-D{r}),IF(D{r}="","",MAX(0,TODAY()-D{r})))')
    dv2 = DataValidation(type="list", formula1='"Draft,Sent,Paid,Overdue"')
    lg.add_data_validation(dv2)
    dv2.add("F2:F201")
    b = io.BytesIO()
    wb.save(b)
    return {"Creator-GST-Invoice-Kit/GST-Invoice-and-Tracker.xlsx": b.getvalue(),
            "Creator-GST-Invoice-Kit/README.txt": "Fill the yellow header, set Place of supply.\nSame state → CGST+SGST split automatically; different state → IGST.\nChange GST rate from the dropdown in F11. Use 'Payment tracker' to chase late payments.\nWorks in Excel, Google Sheets (File → Import) and LibreOffice.\n"}


# ------------------------------------------------------------------ 3. content calendar
def product_calendar():
    wb = Workbook()
    bold = Font(bold=True, color="111709")
    fill = PatternFill("solid", fgColor="D6FF7F")
    plan = wb.active
    plan.title = "Content plan"
    cols = ["Date", "Day", "Platform", "Format", "Pillar", "Hook / title", "Caption", "CTA", "Status", "Link", "Views", "Saves", "Notes"]
    widths = [12, 6, 12, 12, 14, 40, 40, 16, 12, 30, 9, 9, 24]
    for i, (h, w) in enumerate(zip(cols, widths)):
        c = plan.cell(row=1, column=1 + i, value=h)
        c.font, c.fill = bold, fill
        plan.column_dimensions[chr(65 + i)].width = w
    import datetime as dt
    start = dt.date(2026, 10, 1)
    for i in range(365):
        r = i + 2
        plan.cell(row=r, column=1, value=start + dt.timedelta(days=i)).number_format = "DD-MMM-YY"
        plan.cell(row=r, column=2, value=f'=TEXT(A{r},"ddd")')
    for col, opts in (("C", "Instagram,YouTube,Shorts,LinkedIn,X,Threads,Newsletter,Blog"),
                      ("D", "Reel,Carousel,Story,Long video,Short,Post,Live,Thread"),
                      ("E", "Educate,Entertain,Inspire,Behind the scenes,Promote,Community"),
                      ("I", "Idea,Scripted,Shot,Edited,Scheduled,Posted")):
        dv = DataValidation(type="list", formula1=f'"{opts}"')
        plan.add_data_validation(dv)
        dv.add(f"{col}2:{col}366")
    plan.freeze_panes = "A2"
    fest = wb.create_sheet("Festival & event dates")
    events = [("2026-10-02", "Gandhi Jayanti"), ("2026-10-11", "Navratri begins (approx.)"), ("2026-10-20", "Dussehra (approx.)"),
              ("2026-11-08", "Diwali (approx.)"), ("2026-11-14", "Children's Day"), ("2026-11-27", "Black Friday"),
              ("2026-12-25", "Christmas"), ("2027-01-01", "New Year"), ("2027-01-14", "Makar Sankranti / Pongal"),
              ("2027-01-26", "Republic Day"), ("2027-02-14", "Valentine's Day"), ("2027-03-08", "Women's Day"),
              ("2027-03-22", "Holi (approx.)"), ("2027-04-01", "New financial year"), ("2027-05-01", "Labour Day"),
              ("2027-06-21", "Yoga Day"), ("2027-08-15", "Independence Day"), ("2027-09-05", "Teachers' Day")]
    fest.append(["Date", "Event", "Content idea"])
    for c in fest[1]:
        c.font, c.fill = bold, fill
    for d_, e in events:
        fest.append([dt.date.fromisoformat(d_), e, ""])
    fest.column_dimensions["A"].width, fest.column_dimensions["B"].width, fest.column_dimensions["C"].width = 14, 34, 50
    fest["A21"] = "Lunar festival dates vary — confirm each year."
    dash = wb.create_sheet("Dashboard", 0)
    dash["A1"], dash["A1"].font = "Content dashboard", Font(bold=True, size=16)
    stats = [("Posts planned", "=COUNTA('Content plan'!F2:F366)"), ("Posted", "=COUNTIF('Content plan'!I2:I366,\"Posted\")"),
             ("In production", "=COUNTIFS('Content plan'!I2:I366,\"<>Posted\",'Content plan'!I2:I366,\"<>\")"),
             ("Total views", "=SUM('Content plan'!K2:K366)"), ("Total saves", "=SUM('Content plan'!L2:L366)"),
             ("Avg views / post", "=IFERROR(B6/B4,0)")]
    for i, (l, f) in enumerate(stats):
        dash.cell(row=3 + i, column=1, value=l).font = Font(bold=True)
        dash.cell(row=3 + i, column=2, value=f)
    dash.column_dimensions["A"].width = 24
    dash["A11"] = "Per platform"
    dash["A11"].font = Font(bold=True)
    for i, p in enumerate(["Instagram", "YouTube", "Shorts", "LinkedIn", "X", "Threads", "Newsletter", "Blog"]):
        dash.cell(row=12 + i, column=1, value=p)
        dash.cell(row=12 + i, column=2, value=f"=COUNTIF('Content plan'!C2:C366,A{12 + i})")
        dash.cell(row=12 + i, column=3, value=f"=SUMIF('Content plan'!C2:C366,A{12 + i},'Content plan'!K2:K366)")
    b = io.BytesIO()
    wb.save(b)
    return {"Content-Calendar-2026-27/Content-Calendar-Oct2026-Sep2027.xlsx": b.getvalue()}


# ------------------------------------------------------------------ 4. social templates (SVG)
FESTIVALS = [("Happy Diwali", "#1a0f2e", "#ffb347", "diya"), ("Happy Holi", "#101820", "#ff4fa3", "splash"),
             ("Eid Mubarak", "#0c1f1c", "#e8d48b", "moon"), ("Happy Pongal", "#1f1405", "#ffd166", "sun"),
             ("Happy Onam", "#0f1f0c", "#f9c74f", "flower"), ("Happy Independence Day", "#0b1320", "#ff9933", "flag"),
             ("Merry Christmas", "#0d1b14", "#e63946", "star"), ("Happy New Year", "#0b0e13", "#d6ff7f", "spark"),
             ("Ganesh Chaturthi", "#22120a", "#ff8c42", "sun"), ("Navratri Wishes", "#1b0b1f", "#f72585", "flower"),
             ("Raksha Bandhan", "#1a1024", "#ffafcc", "flower"), ("Happy Lohri", "#1d0c05", "#ff7b00", "spark")]


def _motif(kind, c):
    if kind == "diya":
        return f'<ellipse cx="540" cy="700" rx="170" ry="60" fill="{c}"/><path d="M540 470 C600 560 590 640 540 650 C490 640 480 560 540 470Z" fill="#fff3b0"/>'
    if kind == "splash":
        return "".join(f'<circle cx="{540 + math.cos(i) * r:.0f}" cy="{600 + math.sin(i) * r:.0f}" r="{s}" fill="{col}" opacity=".85"/>'
                       for i, r, s, col in [(0.3, 180, 90, c), (2.1, 150, 70, "#4cc9f0"), (3.7, 200, 80, "#ffd60a"), (5.0, 120, 60, "#80ed99"), (1.2, 60, 110, "#b5179e")])
    if kind == "moon":
        return f'<circle cx="540" cy="600" r="170" fill="{c}"/><circle cx="610" cy="560" r="160" fill="#0c1f1c"/><polygon points="700,470 712,505 750,505 720,527 731,562 700,540 669,562 680,527 650,505 688,505" fill="{c}"/>'
    if kind == "sun":
        rays = "".join(f'<line x1="540" y1="600" x2="{540 + math.cos(i * math.pi / 8) * 260:.0f}" y2="{600 + math.sin(i * math.pi / 8) * 260:.0f}" stroke="{c}" stroke-width="10" stroke-linecap="round" opacity=".6"/>' for i in range(16))
        return rays + f'<circle cx="540" cy="600" r="150" fill="{c}"/>'
    if kind == "flower":
        return "".join(f'<ellipse cx="540" cy="480" rx="55" ry="120" fill="{c}" opacity=".85" transform="rotate({a} 540 600)"/>' for a in range(0, 360, 30)) + '<circle cx="540" cy="600" r="60" fill="#fff"/>'
    if kind == "flag":
        return f'<rect x="300" y="470" width="480" height="90" fill="#ff9933"/><rect x="300" y="560" width="480" height="90" fill="#ffffff"/><rect x="300" y="650" width="480" height="90" fill="#138808"/><circle cx="540" cy="605" r="36" fill="none" stroke="#000080" stroke-width="6"/>'
    if kind == "star":
        return f'<polygon points="540,400 590,550 750,550 620,640 670,790 540,700 410,790 460,640 330,550 490,550" fill="{c}"/>'
    return "".join(f'<circle cx="{random.Random(i).randint(150, 930)}" cy="{random.Random(i * 7).randint(380, 820)}" r="{random.Random(i * 3).randint(4, 14)}" fill="{c}" opacity=".9"/>' for i in range(60))


def festival_svg(title, bg, accent, motif, brand="@yourbrand"):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1080" viewBox="0 0 1080 1080">
<defs><radialGradient id="g" cx="50%" cy="55%" r="65%"><stop offset="0" stop-color="{accent}" stop-opacity=".28"/><stop offset="1" stop-color="{bg}" stop-opacity="0"/></radialGradient></defs>
<rect width="1080" height="1080" fill="{bg}"/><rect width="1080" height="1080" fill="url(#g)"/>
<rect x="40" y="40" width="1000" height="1000" rx="28" fill="none" stroke="{accent}" stroke-opacity=".35" stroke-width="2"/>
{_motif(motif, accent)}
<text x="540" y="240" text-anchor="middle" font-family="DejaVu Sans, Arial, sans-serif" font-size="{min(84, int(1500 / max(1, len(title))))}" font-weight="700" fill="#ffffff">{title}</text>
<text x="540" y="310" text-anchor="middle" font-family="DejaVu Sans, Arial, sans-serif" font-size="30" fill="{accent}">Wishing you light, joy and good work</text>
<text x="540" y="980" text-anchor="middle" font-family="DejaVu Sans, Arial, sans-serif" font-size="30" fill="#ffffff" opacity=".8">{brand}</text>
</svg>'''


def product_festival():
    files = {}
    for t, bg, ac, m in FESTIVALS:
        slug = t.replace(" ", "-")
        svg = festival_svg(t, bg, ac, m)
        files[f"Festival-Post-Pack/SVG-editable/{slug}.svg"] = svg
        files[f"Festival-Post-Pack/PNG-1080/{slug}.png"] = png(svg)
    files["Festival-Post-Pack/HOW-TO-EDIT.txt"] = ("Open any SVG in Figma, Illustrator, Inkscape (free) or Canva (upload).\n"
        "Replace '@yourbrand' with your handle and change the greeting line.\nColours are plain hex values in the file — search & replace to rebrand.\n"
        "PNG versions are ready to post (1080×1080).\n")
    return files


def product_carousel():
    files = {}
    themes = [("#0b0e13", "#d6ff7f", "#f4f5f7"), ("#f7f3ea", "#ff5a36", "#1b1b1b"), ("#101a2c", "#7cc6fe", "#ffffff")]
    for ti, (bg, ac, fg) in enumerate(themes, 1):
        slides = [("5 lessons from", "my first year freelancing", "cover"), ("01", "Price the outcome, not the hours", "point"),
                  ("02", "Write every scope in one email", "point"), ("03", "Take 50% upfront. Always.", "point"),
                  ("04", "Your portfolio is your pitch", "point"), ("05", "Say no to ‘exposure’", "point"),
                  ("Save this post", "and follow for more", "cta")]
        for si, (a, b, kind) in enumerate(slides, 1):
            big = 110 if kind == "point" else 76
            svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1350" viewBox="0 0 1080 1350">
<rect width="1080" height="1350" fill="{bg}"/><rect x="80" y="80" width="120" height="12" rx="6" fill="{ac}"/>
<text x="80" y="{560 if kind != 'point' else 470}" font-family="DejaVu Sans, Arial" font-size="{big}" font-weight="700" fill="{ac if kind == 'point' else fg}">{a}</text>
<foreignObject x="80" y="{600 if kind != 'point' else 540}" width="920" height="500"><div xmlns="http://www.w3.org/1999/xhtml" style="font-family:DejaVu Sans,Arial;font-size:64px;font-weight:700;line-height:1.15;color:{fg}">{b}</div></foreignObject>
<text x="80" y="1270" font-family="DejaVu Sans, Arial" font-size="28" fill="{fg}" opacity=".7">@yourhandle</text>
<text x="1000" y="1270" text-anchor="end" font-family="DejaVu Sans, Arial" font-size="28" fill="{fg}" opacity=".7">{si}/{len(slides)}{'  →' if si < len(slides) else ''}</text></svg>'''
            svg_plain = svg.replace(f'<foreignObject x="80" y="{600 if kind != "point" else 540}" width="920" height="500"><div xmlns="http://www.w3.org/1999/xhtml" style="font-family:DejaVu Sans,Arial;font-size:64px;font-weight:700;line-height:1.15;color:{fg}">{b}</div></foreignObject>',
                                    _wrap_text(b, 80, 640 if kind != "point" else 580, 60, fg, 26))
            files[f"Carousel-Kit/Theme-{ti}/slide-{si}.svg"] = svg_plain
            files[f"Carousel-Kit/Theme-{ti}/slide-{si}.png"] = png(svg_plain)
    files["Carousel-Kit/README.txt"] = "3 themes × 7 slides, 1080×1350 (Instagram/LinkedIn portrait). Edit SVGs in Figma/Canva/Inkscape; PNGs are post-ready.\n"
    return files


def _wrap_text(text, x, y, size, fill, width_chars):
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width_chars:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    lines.append(cur)
    return "".join(f'<text x="{x}" y="{y + i * size * 1.2:.0f}" font-family="DejaVu Sans, Arial" font-size="{size}" font-weight="700" fill="{fill}">{ln}</text>' for i, ln in enumerate(lines))


# ------------------------------------------------------------------ 5. gradients
def _mesh(w, h, cols, seed):
    rng = random.Random(seed)
    small = Image.new("RGB", (8, 5))
    px = small.load()
    for x in range(8):
        for y in range(5):
            px[x, y] = tuple(int(c) for c in cols[rng.randrange(len(cols))])
    img = small.resize((w, h), Image.BICUBIC).filter(ImageFilter.GaussianBlur(w / 18))
    noise = Image.effect_noise((w, h), 10).convert("RGB")
    return Image.blend(img, noise, 0.035)


PALETTES = [("Cobalt Night", [(8, 18, 60), (40, 80, 200), (10, 10, 30), (90, 60, 220)]),
            ("Lime Glow", [(20, 30, 10), (214, 255, 127), (60, 90, 30), (15, 20, 12)]),
            ("Saffron Dusk", [(255, 153, 51), (180, 60, 40), (40, 15, 30), (255, 200, 120)]),
            ("Lotus Pink", [(255, 175, 204), (190, 90, 160), (60, 20, 60), (250, 220, 230)]),
            ("Arabian Sea", [(0, 90, 120), (0, 170, 170), (5, 30, 50), (120, 220, 210)]),
            ("Chai", [(120, 70, 40), (210, 160, 110), (50, 30, 20), (240, 220, 190)]),
            ("Neon Street", [(250, 40, 140), (40, 20, 90), (0, 200, 255), (10, 5, 25)]),
            ("Monsoon", [(60, 80, 90), (120, 150, 150), (20, 30, 35), (180, 200, 190)]),
            ("Mango", [(255, 200, 60), (255, 120, 40), (120, 40, 20), (255, 240, 180)]),
            ("Ink & Paper", [(15, 15, 18), (60, 60, 70), (230, 228, 220), (120, 120, 130)]),
            ("Peacock", [(0, 80, 90), (20, 140, 110), (30, 40, 120), (200, 180, 60)]),
            ("Rose Gold", [(230, 170, 150), (180, 110, 110), (70, 40, 50), (250, 220, 200)])]


def product_gradients():
    files, thumbs = {}, []
    for i, (n, cols) in enumerate(PALETTES):
        img = _mesh(2560, 1440, cols, i)
        b = io.BytesIO()
        img.save(b, "PNG", optimize=True)
        slug = n.replace(" ", "-")
        files[f"Gradient-Backgrounds/{slug}-2560x1440.png"] = b.getvalue()
        v = io.BytesIO()
        img.resize((1080, 1920)).save(v, "PNG", optimize=True) if False else _mesh(1080, 1920, cols, i).save(v, "PNG", optimize=True)
        files[f"Gradient-Backgrounds/vertical/{slug}-1080x1920.png"] = v.getvalue()
        thumbs.append(img.resize((256, 144)))
    files["Gradient-Backgrounds/README.txt"] = "12 mesh gradients in 16:9 (2560×1440) and 9:16 (1080×1920). Use for slides, thumbnails, stories, app screens and video backgrounds.\n"
    return files, thumbs


# ------------------------------------------------------------------ 6. lower thirds
def product_lower_thirds():
    files = {}
    styles = [("Minimal Bar", LIME), ("Saffron", "#ff9933"), ("Cobalt", "#4f7cff"), ("Rose", "#ff5d8f"), ("Mono", "#ffffff"), ("Teal", "#2ec4b6")]
    for n, c in styles:
        for variant, (title, sub) in {"name": ("Priya Sharma", "Founder, Studio Ink"), "topic": ("Chapter 02", "Pricing your work")}.items():
            svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">
<rect x="120" y="820" width="10" height="130" fill="{c}"/><rect x="130" y="820" width="720" height="80" fill="#0b0e13" fill-opacity=".86"/>
<rect x="130" y="900" width="560" height="50" fill="{c}" fill-opacity=".92"/>
<text x="160" y="875" font-family="DejaVu Sans, Arial" font-size="46" font-weight="700" fill="#ffffff">{title}</text>
<text x="160" y="936" font-family="DejaVu Sans, Arial" font-size="28" fill="#0b0e13">{sub}</text></svg>'''
            slug = f"{n.replace(' ', '-')}-{variant}"
            files[f"Lower-Thirds/SVG/{slug}.svg"] = svg
            files[f"Lower-Thirds/PNG-alpha-1080p/{slug}.png"] = png(svg)
    files["Lower-Thirds/README.txt"] = ("12 lower thirds (6 styles × name/topic) as transparent 1920×1080 PNGs and editable SVGs.\n"
        "Drop PNGs on a track above your footage in Premiere, Resolve, Final Cut, CapCut or OBS. Edit text in the SVG and re-export.\n")
    return files


# ------------------------------------------------------------------ 7. docs: contract + media kit
def product_contract():
    doc = Document()
    doc.styles["Normal"].font.name = "Arial"
    doc.styles["Normal"].font.size = Pt(10.5)
    doc.add_heading("Creative Services Agreement", 0)
    doc.add_paragraph("Template for freelance creators in India. Not legal advice — review with a lawyer for high-value work.").italic = True
    sections = [
        ("1. Parties", "This Agreement is between [CREATOR NAME], [address], PAN [●] (“Creator”) and [CLIENT NAME], [address], GSTIN [●] (“Client”), effective [DATE]."),
        ("2. Scope of work", "Creator will deliver: [list deliverables, formats, quantities]. Anything not listed is out of scope and will be quoted separately."),
        ("3. Timeline & revisions", "Delivery by [DATE]. Price includes [2] rounds of revisions requested within [5] working days of each delivery. Further revisions are billed at ₹[●]/hour."),
        ("4. Fees & payment", "Total fee ₹[●] plus applicable GST. [50]% is payable before work starts and the balance within [15] days of final delivery. Client may deduct TDS as required by law and will share Form 16A."),
        ("5. Usage rights", "On full payment, Client receives a [non-exclusive / exclusive] licence to use the final deliverables for [organic social / paid media / all media] in [territory] for [duration]. Raw files, project files and unused drafts remain with Creator unless bought out."),
        ("6. Credit", "Creator may display the work in their portfolio after public release, unless a confidentiality period of [●] days is agreed."),
        ("7. Cancellation", "If Client cancels after work starts, the advance is non-refundable and work completed beyond the advance is billed pro rata."),
        ("8. Content approvals & compliance", "Client approves final content before publishing and is responsible for claims about its products. Sponsored content will carry disclosures as required by ASCI guidelines."),
        ("9. Confidentiality", "Both parties will keep non-public information confidential for [2] years."),
        ("10. Liability", "Creator’s total liability is limited to the fees paid under this Agreement."),
        ("11. Governing law", "This Agreement is governed by the laws of India; courts at [CITY] have exclusive jurisdiction."),
    ]
    for h, t in sections:
        doc.add_heading(h, level=2)
        doc.add_paragraph(t)
    doc.add_paragraph("\n\nCreator: ____________________      Client: ____________________\nDate: ____________             Date: ____________")
    b = io.BytesIO()
    doc.save(b)

    kit = Document()
    kit.add_heading("[Your Name] — Media Kit 2026", 0)
    kit.add_paragraph("Creator · [niche] · [city]\n[email] · [website]")
    kit.add_heading("Audience", 1)
    t = kit.add_table(rows=5, cols=4)
    t.style = "Light Grid Accent 1"
    for i, r in enumerate([["Platform", "Followers", "Avg views", "Engagement"], ["Instagram", "", "", ""], ["YouTube", "", "", ""],
                           ["LinkedIn", "", "", ""], ["Newsletter", "", "Open rate", ""]]):
        for j, v in enumerate(r):
            t.cell(i, j).text = v
    kit.add_paragraph("Top cities: ____   Age 18–24: __%  25–34: __%   Gender split: __/__")
    kit.add_heading("Rate card", 1)
    t2 = kit.add_table(rows=7, cols=3)
    t2.style = "Light Grid Accent 1"
    for i, r in enumerate([["Deliverable", "Includes", "Rate (₹)"], ["Instagram Reel", "Concept, shoot, edit, 1 revision", ""],
                           ["Carousel (7 slides)", "Copy + design", ""], ["Story set (3)", "With link sticker", ""],
                           ["YouTube integration (60–90s)", "Scripted mid-roll", ""], ["Usage rights (paid ads, 3 months)", "Whitelisting", "+__%"],
                           ["Bundle", "Reel + 3 stories + carousel", ""]]):
        for j, v in enumerate(r):
            t2.cell(i, j).text = v
    kit.add_heading("Past partners", 1)
    kit.add_paragraph("[Brand 1] · [Brand 2] · [Brand 3]")
    b2 = io.BytesIO()
    kit.save(b2)
    return {"Freelance-Business-Pack/Creative-Services-Agreement.docx": b.getvalue(),
            "Freelance-Business-Pack/Media-Kit-and-Rate-Card.docx": b2.getvalue()}


# ------------------------------------------------------------------ 8. prompts
PROMPTS = {
    "Hooks": ["Write 10 scroll-stopping hooks for a Reel about {topic} for {audience}. Max 8 words each. Mix curiosity, contrarian and number-led hooks.",
              "Rewrite this hook 5 ways, each under 10 words, keeping the promise but increasing tension: {hook}",
              "Give me 7 YouTube titles for a video on {topic}. Under 60 characters, no clickbait that the video can't deliver."],
    "Scripts": ["Write a 45-second Reel script on {topic}: hook (0–3s), problem, 3 quick tips with on-screen text, CTA. Conversational Indian English.",
                "Turn this blog post into a 60-second talking-head script with B-roll suggestions in brackets: {text}",
                "Write a YouTube intro (first 30s) for {topic} that states the payoff, proves credibility and previews the steps."],
    "Captions": ["Write an Instagram caption for {post}. First line is a hook, 3 short paragraphs, 1 question to drive comments, 5 relevant hashtags.",
                 "Write a LinkedIn post from this idea: {idea}. Short lines, one personal story, one takeaway, no hashtags spam."],
    "Repurposing": ["Turn this YouTube transcript into: 1 carousel (7 slides), 3 tweets, 1 newsletter intro. Transcript: {text}",
                    "Extract 5 quotable lines (under 20 words) from this podcast transcript for quote cards: {text}"],
    "Business": ["Draft a polite follow-up email for an unpaid invoice of ₹{amount} that is {days} days overdue. Firm, friendly, with payment link.",
                 "Write a brand pitch email to {brand} for a {deliverable} collaboration. Include my audience stats: {stats}. Under 150 words.",
                 "Create a 3-tier pricing table (Basic/Standard/Premium) for {service} with clear deliverables and revision limits.",
                 "Reply to this client asking for 'a small change' that is actually out of scope. Keep the relationship warm: {message}"],
    "Design & AI art": ["Write a detailed image-generation prompt for a product render of {product}: materials, lighting, lens, background, mood.",
                        "Give me 5 colour palettes (hex) for a {brand_type} brand that feels {adjectives}. Explain each in one line.",
                        "Describe a thumbnail concept for a video titled '{title}': subject, expression, text (max 4 words), contrast."],
    "Planning": ["Build a 4-week content plan for {niche} on {platform}: 3 posts/week, mixed pillars (educate/entertain/promote), with hooks.",
                 "List 20 content ideas for {niche} tied to Indian festivals and events in {month}."],
}


def product_prompts():
    md = ["# Creator Prompt Library\n", "Fill the {placeholders}. Works with ChatGPT, Claude, Gemini and other assistants.\n"]
    data = []
    for cat, ps in PROMPTS.items():
        md.append(f"\n## {cat}\n")
        for p in ps:
            md.append(f"- {p}\n")
            data.append({"category": cat, "prompt": p})
    return {"Creator-Prompt-Library/prompts.md": "".join(md), "Creator-Prompt-Library/prompts.json": json.dumps(data, indent=2, ensure_ascii=False)}


# ------------------------------------------------------------------ 9. brand palette tokens (free)
def product_palettes():
    rng = random.Random(7)
    out, css = [], [":root {"]
    for n, cols in PALETTES:
        hexes = ["#%02x%02x%02x" % c for c in cols]
        out.append({"name": n, "colors": hexes})
        for i, h in enumerate(hexes):
            css.append(f"  --{n.lower().replace(' ', '-').replace('&', 'and')}-{i + 1}: {h};")
    css.append("}")
    sw = Image.new("RGB", (1200, 60 * len(PALETTES)), INK)
    d = ImageDraw.Draw(sw)
    f = ImageFont.truetype(FONT, 18)
    for r, p in enumerate(out):
        d.text((16, r * 60 + 20), p["name"], font=f, fill=PAPER)
        for i, h in enumerate(p["colors"]):
            d.rectangle([260 + i * 230, r * 60 + 8, 480 + i * 230, r * 60 + 52], fill=h)
            d.text((270 + i * 230, r * 60 + 20), h, font=f, fill="#000" if sum(int(h[k:k + 2], 16) for k in (1, 3, 5)) > 380 else "#fff")
    b = io.BytesIO()
    sw.save(b, "PNG")
    tokens = {"color": {p["name"]: {str(i + 1): {"value": h, "type": "color"} for i, h in enumerate(p["colors"])} for p in out}}
    _ = rng
    return {"Brand-Palettes/palettes.json": json.dumps(out, indent=2), "Brand-Palettes/palettes.css": "\n".join(css) + "\n",
            "Brand-Palettes/figma-tokens.json": json.dumps(tokens, indent=2), "Brand-Palettes/swatches.png": b.getvalue()}


# ------------------------------------------------------------------ covers
def _doc_art(kind: str, accent: str, W=1536, H=600) -> Image.Image:
    """Simple illustration for products without visual previews (sheets, docs, prompts)."""
    img = Image.new("RGB", (W, H), "#0b0e13")
    d = ImageDraw.Draw(img)
    f, fb = ImageFont.truetype(FONT, 22), ImageFont.truetype(FONT_B, 24)
    x0, y0, w, h = 330, 70, 880, 500
    d.rounded_rectangle([x0, y0, x0 + w, y0 + h], 18, fill="#151b24", outline="#2b3440", width=2)
    if kind == "sheet":
        cols = [0, 70, 420, 560, 700, 880]
        for i in range(10):
            y = y0 + 20 + i * 46
            if i == 0:
                d.rectangle([x0 + 10, y, x0 + w - 10, y + 40], fill=accent)
            for c in cols[1:-1]:
                d.line([x0 + c, y0 + 20, x0 + c, y0 + 20 + 460], fill="#2b3440", width=1)
            d.line([x0 + 10, y + 44, x0 + w - 10, y + 44], fill="#2b3440", width=1)
        for i, t in enumerate(["#", "Description", "SAC", "Qty", "Amount"]):
            d.text((x0 + cols[i] + 16, y0 + 28), t, font=fb, fill="#111709")
        rows = [("1", "Reel — concept & edit", "998361", "2", "24,000"), ("2", "Thumbnail design", "998391", "4", "6,000"),
                ("3", "Usage rights · 6 mo", "997331", "1", "8,000"), ("", "CGST 9%", "", "", "3,420"), ("", "SGST 9%", "", "", "3,420"),
                ("", "TOTAL", "", "", "44,840")]
        for r, row in enumerate(rows):
            for i, t in enumerate(row):
                d.text((x0 + cols[i] + 16, y0 + 74 + r * 46), t, font=fb if row[1] == "TOTAL" else f,
                       fill=accent if row[1] == "TOTAL" else "#d7dee8")
    elif kind == "calendar":
        d.text((x0 + 30, y0 + 22), "OCTOBER 2026", font=fb, fill=accent)
        for i, dn in enumerate("MTWTFSS"):
            d.text((x0 + 40 + i * 120, y0 + 70), dn, font=f, fill="#8e9aad")
        tags = {2: "Reel", 5: "Carousel", 9: "Short", 11: "Navratri", 16: "Live", 20: "Dussehra", 23: "Reel", 27: "Post"}
        for day in range(1, 32):
            c, r = (day + 2) % 7, (day + 2) // 7
            x, y = x0 + 30 + c * 120, y0 + 110 + r * 72
            d.rounded_rectangle([x, y, x + 110, y + 64], 8, fill="#1c2430")
            d.text((x + 8, y + 6), str(day), font=f, fill="#d7dee8")
            if day in tags:
                d.rounded_rectangle([x + 6, y + 36, x + 104, y + 58], 6, fill=accent)
                d.text((x + 12, y + 37), tags[day], font=ImageFont.truetype(FONT, 16), fill="#111709")
    else:  # doc / prompts
        lines = {"doc": ["CREATIVE SERVICES AGREEMENT", "1. Scope of work", "2. Timeline & revisions", "3. Fees: 50% advance, TDS",
                         "4. Usage rights & credit", "5. Cancellation", "6. Governing law — India"],
                 "prompts": ["> Write 10 scroll-stopping hooks for", "  a Reel about {topic} for {audience}", "",
                             "> Draft a polite follow-up for an", "  unpaid invoice of ₹{amount}, {days} days overdue", "",
                             "> Turn this transcript into a carousel"]}[kind]
        for i, t in enumerate(lines):
            d.text((x0 + 44, y0 + 40 + i * 62), t, font=fb if i == 0 else f, fill=accent if i == 0 else "#d7dee8")
    return img


def cover(title, subtitle, accent, bg="#0b0e13", art=None) -> bytes:
    W, H = 1536, 1024
    band = int(H * 0.36)
    img = Image.new("RGB", (W, H), bg)
    if isinstance(art, str):
        art = _doc_art(art, accent)
    if art is not None:
        a = art.convert("RGB").copy()
        a.thumbnail((W - 120, H - band - 70))
        img.paste(a, ((W - a.width) // 2, 40 + (H - band - 70 - a.height) // 2))
    d = ImageDraw.Draw(img)
    d.rectangle([0, H - band, W, H], fill="#080a0e")
    d.line([0, H - band, W, H - band], fill="#232831", width=2)
    y = H - band + 58
    d.rectangle([80, y, 200, y + 12], fill=accent)
    d.text((80, y + 36), title, font=ImageFont.truetype(FONT_B, 76), fill="#ffffff")
    d.text((82, y + 138), subtitle, font=ImageFont.truetype(FONT, 36), fill="#c9d1db")
    d.text((W - 80, y + 2), "SMARTSHARING STUDIO", font=ImageFont.truetype(FONT_B, 22), fill=accent, anchor="ra")
    b = io.BytesIO()
    img.save(b, "WEBP", quality=86)
    return b.getvalue()


def grid(images: list[Image.Image], cols: int, W=1536, H=1024, bg=(11, 14, 19)) -> Image.Image:
    rows = math.ceil(len(images) / cols)
    canvas = Image.new("RGB", (W, H), bg)
    cw, ch = W // cols, H // rows
    for i, im in enumerate(images):
        t = im.convert("RGB").copy()
        t.thumbnail((cw - 16, ch - 16))
        canvas.paste(t, ((i % cols) * cw + (cw - t.width) // 2, (i // cols) * ch + (ch - t.height) // 2))
    return canvas


def _png_to_img(b: bytes) -> Image.Image:
    return Image.open(io.BytesIO(b))


# ------------------------------------------------------------------ catalogue
def build(only: set[str] | None = None):
    need = lambda *ids: only is None or bool(only & set(ids))  # noqa: E731
    lut_files, lut_tiles = product_luts() if need("cinematic-luts-vol1") else ({}, [])
    grad_files, grad_thumbs = product_gradients() if need("gradient-backgrounds") else ({}, [])
    fest = product_festival() if need("festival-post-pack") else {}
    car = product_carousel() if need("carousel-kit") else {}
    lt = product_lower_thirds() if need("lower-thirds-pack") else {}
    pal = product_palettes() if need("brand-palettes") else {"Brand-Palettes/swatches.png": png('<svg xmlns="http://www.w3.org/2000/svg" width="2" height="2"/>')}
    lazy = {"gst-invoice-kit": product_invoice, "content-calendar-2026": product_calendar,
            "freelance-business-pack": product_contract, "creator-prompt-library": product_prompts}
    F = {k: (fn() if need(k) else {}) for k, fn in lazy.items()}
    items = [
        dict(id="cinematic-luts-vol1", name="Cinematic LUTs Vol. 1", category="Motion & video", kind="file", price=349,
             format="CUBE · 10 LUTs · 33-point", files=lut_files, affiliate_pct=20,
             description="Ten 33-point .cube grades built for Indian light: Monsoon Teal, Golden Hour Warm, Bollywood Pop, Kerala Green, Night Street Neon and more. Works in Premiere Pro, DaVinci Resolve, Final Cut, CapCut and LumaFusion.",
             includes=["10 .cube LUTs (Rec.709)", "Preview sheet", "Install guide for 5 editors"],
             cover=("Cinematic LUTs", "10 grades · Premiere · Resolve · FCP", "#2ec4b6", grid([t for _, t in lut_tiles], 5, W=1536, H=340))),
        dict(id="gst-invoice-kit", name="Creator GST Invoice Kit", category="Business & finance", kind="file", price=199,
             format="XLSX · Excel & Google Sheets", files=F["gst-invoice-kit"], affiliate_pct=25,
             description="A tax invoice that fills in CGST+SGST or IGST automatically based on place of supply, with SAC codes, optional TDS line, due-date maths and a payment tracker that flags overdue clients.",
             includes=["Auto GST split (same state / inter-state)", "Payment tracker with days-late", "Works in Excel, Sheets, LibreOffice"],
             cover=("GST Invoice Kit", "Auto CGST/SGST/IGST · payment tracker", "#d6ff7f", "sheet")),
        dict(id="content-calendar-2026", name="Content Calendar 2026–27", category="Business & finance", kind="file", price=0,
             format="XLSX · 365-day planner", files=F["content-calendar-2026"],
             description="A year-long planner from October 2026 with platform, format and status dropdowns, a festival date sheet for India and an auto dashboard for posts, views and saves per platform. Free.",
             includes=["365 dated rows with dropdowns", "Festival & event dates", "Auto dashboard"],
             cover=("Content Calendar", "Oct 2026 – Sep 2027 · free", "#ffd166", "calendar")),
        dict(id="festival-post-pack", name="Indian Festival Post Pack", category="Templates", kind="file", price=299,
             format="SVG + PNG · 12 posts · 1080×1080", files=fest, affiliate_pct=20,
             description="Twelve ready-to-post greetings — Diwali, Holi, Eid, Pongal, Onam, Independence Day, Ganesh Chaturthi, Navratri, Raksha Bandhan, Lohri, Christmas and New Year — as editable SVGs plus PNGs.",
             includes=["12 editable SVG posts", "12 PNGs ready to post", "Rebrand with one colour swap"],
             cover=("Festival Post Pack", "12 greetings · editable SVG + PNG", "#ffb347",
                    grid([_png_to_img(v) for k, v in fest.items() if k.endswith(".png")][:12], 6, W=1536, H=560))),
        dict(id="carousel-kit", name="Carousel Template Kit", category="Templates", kind="file", price=249,
             format="SVG + PNG · 3 themes × 7 slides", files=car,
             description="Portrait 1080×1350 carousel templates for Instagram and LinkedIn: cover, five point slides and a save/follow CTA in three colour themes. Edit in Figma, Canva or Inkscape.",
             includes=["21 slides in 3 themes", "Editable SVG + PNG", "Slide counter and handle built in"],
             cover=("Carousel Kit", "Instagram & LinkedIn · 3 themes", "#ff5a36",
                    grid([_png_to_img(v) for k, v in car.items() if k.endswith(".png") and "Theme-1" in k][:4] + [_png_to_img(v) for k, v in car.items() if k.endswith("slide-2.png")][1:3], 6, W=1536, H=420))),
        dict(id="gradient-backgrounds", name="Mesh Gradient Backgrounds", category="3D & design", kind="file", price=149,
             format="PNG · 12 × (16:9 + 9:16)", files=grad_files,
             description="Twelve soft mesh gradients — Cobalt Night, Saffron Dusk, Arabian Sea, Chai, Peacock and more — in 2560×1440 and 1080×1920 for slides, thumbnails, stories and app screens.",
             includes=["12 landscape 2560×1440", "12 vertical 1080×1920", "Subtle grain for no banding"],
             cover=("Mesh Gradients", "12 palettes · landscape + vertical", "#7cc6fe", grid(grad_thumbs, 6, W=1536, H=420))),
        dict(id="lower-thirds-pack", name="Lower Thirds Pack", category="Motion & video", kind="file", price=199,
             format="PNG alpha + SVG · 12 titles", files=lt,
             description="Clean name and chapter lower thirds in six styles as transparent 1080p PNGs and editable SVGs. Drop onto Premiere, Resolve, Final Cut, CapCut or OBS.",
             includes=["6 styles × name/topic", "Transparent 1920×1080 PNG", "Editable SVG"],
             cover=("Lower Thirds", "6 styles · transparent 1080p", "#ff5d8f",
                    grid([_png_to_img(v).crop((100, 780, 900, 980)) for k, v in lt.items() if k.endswith("-name.png")][:6], 3, W=1536, H=400))),
        dict(id="freelance-business-pack", name="Freelance Contract & Media Kit", category="Business & finance", kind="file", price=299,
             format="DOCX · contract + media kit", files=F["freelance-business-pack"], affiliate_pct=25,
             description="A creative services agreement written for Indian freelancers (scope, revisions, 50% advance, TDS, usage rights, ASCI disclosure) plus a media kit and rate card you can fill in and send today.",
             includes=["11-clause services agreement", "Media kit + rate card", "Editable in Word & Google Docs"],
             cover=("Contract + Media Kit", "For Indian freelancers & creators", "#e8d48b", "doc")),
        dict(id="creator-prompt-library", name="Creator Prompt Library", category="AI workflows", kind="file", price=0,
             format="MD + JSON · 20 prompts", files=F["creator-prompt-library"],
             description="Tested prompts for hooks, scripts, captions, repurposing, pricing, client emails and thumbnails. Paste into ChatGPT, Claude or Gemini and fill the placeholders. Free.",
             includes=["7 categories", "Markdown + JSON (for Notion/automation)", "Indian context examples"],
             cover=("Prompt Library", "Hooks · scripts · client emails · free", "#b8bcf7", "prompts")),
        dict(id="brand-palettes", name="Brand Palette Tokens", category="3D & design", kind="file", price=99,
             format="JSON · CSS · Figma tokens", files=pal,
             description="Twelve four-colour palettes as CSS variables, Figma/Tokens Studio JSON and a swatch sheet — drop straight into a website, deck or design system.",
             includes=["palettes.css variables", "Figma tokens JSON", "Swatch sheet PNG"],
             cover=("Brand Palettes", "CSS · Figma tokens · swatches", "#d6ff7f", _png_to_img(pal["Brand-Palettes/swatches.png"]))),
    ]
    return [i for i in items if only is None or i["id"] in only]


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="product ids to rebuild")
    args = ap.parse_args()
    d = get_db()
    ensure_indexes(d)
    ensure_platform_account(d)
    studio = d.users.find_one({"handle": "smartsharing.studio"})
    if not studio:
        studio = create_user(d, full_name="SmartSharing Studio", email=None, password_hash=None, handle="smartsharing.studio",
                             opening_credits=0, profile={"role": "Official store", "is_official": True, "city": "Bengaluru",
                                                         "country": "India", "bio": "Original templates, grades and business tools made by the SmartSharing team."})
    covers = storage.STORAGE / "covers"
    covers.mkdir(parents=True, exist_ok=True)
    for p in build(set(args.only) if args.only else None):
        title, sub, accent, art = p.pop("cover")
        (covers / f"{p['id']}.webp").write_bytes(cover(title, sub, accent, art=art))
        zname = p["name"].replace(" ", "-").replace("&", "and").replace("–", "-") + ".zip"
        meta = storage.save_bytes(p["id"], zname, zip_bytes(p.pop("files")))
        meta["name"] = zname
        image = f"/media/covers/{p['id']}.webp"
        existing = d.assets.find_one({"_id": p["id"]})
        if existing:
            for f in existing.get("files", []):
                if f["path"] != meta["path"]:
                    storage.delete(f["path"])
            d.assets.update_one({"_id": p["id"]}, {"$set": {**{k: p[k] for k in ("name", "description", "price", "format", "includes", "category", "kind")},
                                                             "files": [meta], "image": image, "status": "published", "is_official": True,
                                                             "affiliate_pct": p.get("affiliate_pct", 0), "updated_at": now_utc()}})
            print("updated", p["id"], f"{meta['size'] / 1024:.0f} KB")
        else:
            create_asset(d, studio, asset_id=p["id"], name=p["name"], category=p["category"], description=p["description"],
                         price=p["price"], kind=p["kind"], format=p["format"], includes=p["includes"], image=image,
                         files=[meta], affiliate_pct=p.get("affiliate_pct", 0), tag="SMARTSHARING STUDIO")
            print("created", p["id"], f"{meta['size'] / 1024:.0f} KB")


if __name__ == "__main__":
    main()
