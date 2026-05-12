"""
admin_server.py — DataJobs Africa Admin Panel
==============================================
Features:
  - Add / Delete job offers
  - Auto-saves to offres.json
  - Auto-push to GitHub (optional)
  - WhatsApp message generator (copy/download)
  - Checkbox selection of offers
  - Generate job image per offer (2 templates, alternating colors)
  - Generate PDF with selected offers
  - Auto-maintenance (isNew badge, expired flag)

Usage:
  pip install flask pillow fpdf2
  python admin_server.py
  Open http://localhost:5000
"""

from flask import Flask, render_template_string, request, redirect, url_for, jsonify, send_file, Response
import json, os, datetime, subprocess, io

app = Flask(__name__)

# ─────────────────────────────────────────────────
#  CONFIG — EDIT THESE
# ─────────────────────────────────────────────────
JSON_FILE = r"C:\Users\fokam\OneDrive\Bureau\DataJobsAfrica\datajobsafrica.github.io\offres.json"
SITE_URL      = "https://datajobsafrica.github.io"
FACEBOOK_URL  = "https://tinyurl.com/3urze6e5"
LINKEDIN_URL  = "https://www.linkedin.com/in/datajobs-africa-225789409"
WHATSAPP_URL  = "https://YOUR_WHATSAPP_LINK"

GITHUB_ENABLED    = True
GITHUB_REPO_PATH = r"C:\Users\fokam\OneDrive\Bureau\DataJobsAfrica\datajobsafrica.github.io"
GITHUB_BRANCH     = "main"
NEW_BADGE_DAYS    = 1

# ─────────────────────────────────────────────────
#  TYPE GROUPS — DataJobs Africa (no Economics)
# ─────────────────────────────────────────────────
TYPE_GROUPS = {
    "🖥 Technology & Data": {
        "data-science":   "Data Science",
        "ia":             "AI / Machine Learning",
        "ingenierie":     "Data Engineering",
        "analytics":      "Analytics / BI",
    },
    "🌍 International Development": {
        "meal":           "Monitoring & Evaluation",
        "research":       "Research",
        "prog-data":      "Programme Data Mgmt",
    },
    "🏥 Public Health & Social Sciences": {
        "epidemiology":   "Epidemiology & Health Data",
        "biostatistics":  "Biostatistics",
        "demography":     "Demography & Population",
        "social-research":"Social Research & Surveys",
    },
    "📊 Statistics & Quantitative Methods": {
        "official-stats": "Official Statistics",
        "survey":         "Survey & Sampling Methods",
        "actuarial":      "Actuarial & Risk Analysis",
    },
}
TYPE_LABELS = {k: v for g in TYPE_GROUPS.values() for k, v in g.items()}

# ─────────────────────────────────────────────────
#  IMAGE COLORS (2 templates alternating)
# ─────────────────────────────────────────────────
COLORS = [
    # LIGHT — like Job_4
    {"bg":(245,247,250),"card":(255,255,255),"nav":(13,43,31),
     "acc":(0,168,107),"gold":(255,184,0),"txt":(26,42,50),
     "mut":(74,98,114),"dark":False},
    # DARK — like Job_5 / Job_9
    {"bg":(13,43,31),"card":(10,34,22),"nav":(8,26,16),
     "acc":(0,168,107),"gold":(255,184,0),"txt":(255,255,255),
     "mut":(144,200,160),"dark":True},
]

# ─────────────────────────────────────────────────
#  FILE OPS
# ─────────────────────────────────────────────────
def load_jobs():
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE,"r",encoding="utf-8") as f:
            return json.load(f)
    return []

def save_jobs(jobs):
    with open(JSON_FILE,"w",encoding="utf-8") as f:
        json.dump(jobs,f,ensure_ascii=False,indent=2)

# ─────────────────────────────────────────────────
#  GITHUB PUSH
# ─────────────────────────────────────────────────
def github_push(message=None):
    if not GITHUB_ENABLED:
        return {"success":False,"msg":"GitHub push disabled"}
    try:
        msg = message or "chore: update offres.json via admin"
        # 1. On récupère les éventuelles modifs sur GitHub pour éviter le conflit
        subprocess.run(["git", "-C", GITHUB_REPO_PATH, "pull", "origin", GITHUB_BRANCH, "--rebase"], check=True)
        
        # 2. On ajoute les fichiers
        subprocess.run(["git", "-C", GITHUB_REPO_PATH, "add", "."], check=True)
        
        # 3. On commit (on ignore l'erreur si rien n'a changé)
        subprocess.run(["git", "-C", GITHUB_REPO_PATH, "commit", "-m", msg], capture_output=True)
        
        # 4. On pousse vers GitHub
        subprocess.run(["git", "-C", GITHUB_REPO_PATH, "push", "origin", GITHUB_BRANCH], check=True)
        return {"success":True, "msg":f"✅ Pushed to GitHub ({GITHUB_BRANCH})"}
    except Exception as e:
        return {"success":False, "msg":f"❌ Git error: {e}"}

# ─────────────────────────────────────────────────
#  AUTO-MAINTENANCE
# ─────────────────────────────────────────────────
def auto_maintain(jobs):
    today = datetime.date.today()
    changed = False
    for j in jobs:
        if j.get("isNew"):
            try:
                p = j.get("date","").split("/")
                added = datetime.date(int(p[2]),int(p[1]),int(p[0]))
                if (today - added).days > NEW_BADGE_DAYS:
                    j["isNew"] = False; changed = True
            except: pass
        dl = j.get("deadline","")
        if dl and dl not in ["Not specified","Non spécifiée",""]:
            try:
                if datetime.date.fromisoformat(dl) < today and not j.get("expired"):
                    j["expired"] = True; changed = True
            except: pass
    return jobs, changed

# ─────────────────────────────────────────────────
#  WHATSAPP MESSAGE
# ─────────────────────────────────────────────────
def build_whatsapp(job):
    tl = TYPE_LABELS.get(job.get("type",""), job.get("type","N/A"))
    lines = [
        "📢 *NEW JOB ALERT*\n",
        f"🏷️ *Position* : {job.get('title','N/A')}",
        f"🏢 *Company*  : {job.get('company','N/A')}",
        f"📍 *Location* : {job.get('location','N/A')}",
        f"📂 *Type*     : {tl}",
        f"👤 *Level*    : {job.get('level','N/A')}",
    ]
    dl = job.get("deadline","")
    if dl and dl not in ["Not specified","Non spécifiée",""]:
        lines.append(f"⏰ *Deadline* : {dl}")
    sal = job.get("salary","")
    if sal and sal not in ["Not specified","Non spécifié",""]:
        lines.append(f"💰 *Salary*   : {sal}")
    if job.get("remote"):
        lines.append("🌐 *Remote*   : Yes")
    if job.get("instructions"):
        lines.append(f"\n📝 *Instructions* : {job['instructions']}")
    if job.get("contactEmail"):
        lines.append(f"📧 *Email* : {job['contactEmail']}")
    if job.get("summary"):
        s = job["summary"][:220] + ("…" if len(job["summary"])>220 else "")
        lines.append(f"\n📌 *Summary* :\n{s}")
    # Social order: Site → Facebook → LinkedIn → WhatsApp
    lines += [
        f"\n🔗 *Site*      : {SITE_URL}#offres",
        f"👍 *Facebook*  : {FACEBOOK_URL}",
        f"💼 *LinkedIn*  : {LINKEDIN_URL}",
        f"📲 *WhatsApp*  : {WHATSAPP_URL}",
        "\n" + "─"*40,
    ]
    return "\n".join(lines)

# ─────────────────────────────────────────────────
#  IMAGE GENERATION (Pillow)
# ─────────────────────────────────────────────────
def generate_job_image(job, color_idx=0):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return None, "Pillow not installed. Run: pip install pillow"

    C = COLORS[color_idx % len(COLORS)]
    W, H = 1080, 1080
    img = Image.new("RGB",(W,H),C["bg"])
    draw = ImageDraw.Draw(img)

    def fnt(size, bold=False):
        candidates = [
            ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
             else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            ("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
            ("/System/Library/Fonts/Helvetica.ttc"),
        ]
        for path in candidates:
            if os.path.exists(path):
                try: return ImageFont.truetype(path, size)
                except: pass
        return ImageFont.load_default()

    fn_brand  = fnt(44, bold=True)
    fn_tag    = fnt(22, bold=True)
    fn_tagline= fnt(32, bold=True)
    fn_label  = fnt(26, bold=True)
    fn_value  = fnt(26)
    fn_small  = fnt(21)
    fn_tiny   = fnt(17)
    fn_url    = fnt(19)

    acc  = C["acc"]
    gold = C["gold"]
    txt  = C["txt"]
    mut  = C["mut"]
    nav  = C["nav"]
    dark = C["dark"]

    # ── HEADER ──
    draw.rectangle([0,0,W,165], fill=nav)
    draw.rectangle([0,161,W,166], fill=acc)
    draw.rectangle([0,166,W,170], fill=gold)

    # Brand left
    brand_x = 44
    dj_w = int(draw.textlength("DataJobs", font=fn_brand))
    draw.text((brand_x, 28), "DataJobs", font=fn_brand, fill=acc)
    draw.text((brand_x + dj_w, 28), ".Africa", font=fn_brand, fill=(255,255,255))
    draw.text((brand_x+2, 82), "DATA  •  TECH  •  AI  •  AFRICA", font=fn_tiny, fill=(60,120,80))

    # Tagline right
    draw.text((W-420, 38), "Dream Big,", font=fn_tagline, fill=(255,255,255))
    draw.text((W-390, 82), "Think Sharp", font=fn_tagline, fill=acc)

    # Africa dots decoration (top right)
    import random
    rng = random.Random(99)
    for _ in range(200):
        dx = rng.randint(680, 1060)
        dy = rng.randint(8, 158)
        r  = rng.randint(1,3)
        a  = rng.randint(30,110)
        draw.ellipse([dx-r,dy-r,dx+r,dy+r], fill=(*acc,a))

    # ── JOB ALERT BADGE ──
    bx,by = 44,192
    draw.rounded_rectangle([bx,by,bx+275,by+56], radius=28, outline=acc, width=3,
                            fill=rgba(acc,20) if not dark else rgba(acc,30))
    draw.text((bx+16, by+12), "🔔  JOB ALERT", font=fn_label, fill=acc)

    # ── CARD ──
    cy = 268
    card_fill = C["card"]
    card_outline = acc if not dark else (30,80,50)
    draw.rounded_rectangle([28,cy,W-28,H-148], radius=22, fill=card_fill,
                            outline=card_outline, width=2)

    # ── FIELDS ──
    fields = []
    fields.append(("💼  Position", (job.get("title") or "N/A").upper()))
    fields.append(("🏢  Company",  job.get("company") or "N/A"))
    fields.append(("📍  Location", job.get("location") or job.get("country") or "N/A"))
    fields.append(("📊  Type",     TYPE_LABELS.get(job.get("type",""), job.get("type","N/A"))))
    fields.append(("👤  Level",    job.get("level") or "N/A"))
    dl = job.get("deadline","")
    fields.append(("📅  Deadline", dl if dl and dl not in ["Not specified","Non spécifiée",""] else "Not specified"))
    sal = job.get("salary","")
    if sal and sal not in ["Not specified","Non spécifié",""]:
        fields.append(("💰  Salary", sal))
    if job.get("remote"):
        fields.append(("🌐  Remote",  "Yes — Remote work available"))

    row_h = 62
    y = cy + 22
    lbl_color = mut
    val_color = acc
    sep_color = (200,225,210) if not dark else (25,65,45)

    for lbl, val in fields:
        draw.text((62, y), lbl + " :", font=fn_label, fill=lbl_color)
        if len(val) > 44: val = val[:43]+"…"
        draw.text((330, y), val, font=fn_value, fill=val_color)
        draw.line([62, y+row_h-8, W-62, y+row_h-8], fill=sep_color, width=1)
        y += row_h

    # ── SUMMARY ──
    summary = job.get("summary","")
    if summary and y < H - 250:
        y += 8
        draw.text((62, y), "📋  Summary :", font=fn_label, fill=lbl_color)
        y += 32
        words = summary.split()
        line, out = "", []
        for w in words:
            test = line + (" " if line else "") + w
            if draw.textlength(test, font=fn_small) < W - 124:
                line = test
            else:
                out.append(line); line = w
            if len(out) >= 3: break
        if line and len(out) < 3: out.append(line)
        if len(out) == 3: out[-1] += "…"
        for l in out:
            if y < H - 180:
                draw.text((62, y), l, font=fn_small, fill=txt)
                y += 28

    # ── FOOTER ──
    fy = H - 140
    draw.rectangle([0, fy, W, H], fill=(6,20,12) if dark else nav)
    draw.rectangle([0, fy, W, fy+3], fill=gold)

    # Social links — order: Site, Facebook, LinkedIn, WhatsApp
    socials = [
        ("🌐 Site",      SITE_URL.replace("https://","")[:28]),
        ("📘 Facebook",  FACEBOOK_URL.replace("https://","")[:28]),
        ("💼 LinkedIn",  "linkedin.com/in/datajobs-africa"),
        ("💬 WhatsApp",  "Join our channel"),
    ]
    col = W // 4
    for i,(name,url) in enumerate(socials):
        fx = i*col + 18
        draw.text((fx, fy+12), name, font=fn_tiny, fill=(160,210,175))
        draw.text((fx, fy+36), url, font=fn_url, fill=acc)

    # Bottom note
    note = "Rejoignez la communauté des talents data, tech & AI en Afrique."
    note_w = int(draw.textlength(note, font=fn_tiny))
    draw.text(((W-note_w)//2, fy+74), note, font=fn_tiny, fill=(60,120,80))

    buf = io.BytesIO()
    img.save(buf, format="PNG", dpi=(150,150))
    buf.seek(0)
    return buf, None

def rgba(color, alpha):
    """Return fill with pseudo alpha blending for PIL."""
    return color  # PIL doesn't support RGBA in RGB mode; kept for clarity

# ─────────────────────────────────────────────────
#  PDF GENERATION (fpdf2)
# ─────────────────────────────────────────────────
def generate_pdf(jobs):
    try:
        from fpdf import FPDF
    except ImportError:
        return None, "fpdf2 not installed. Run: pip install fpdf2"

    GREEN = (13,107,58); DARK=(13,43,31); GOLD=(200,150,0)
    WHITE=(255,255,255); MUTED=(74,98,114)

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)

    for job in jobs:
        pdf.add_page()

        # Header
        pdf.set_fill_color(*DARK)
        pdf.rect(0,0,210,28,style="F")
        pdf.set_fill_color(*GOLD)
        pdf.rect(0,27,210,1.2,style="F")
        pdf.set_fill_color(*GREEN)
        pdf.rect(0,28.2,210,0.8,style="F")

        # Brand
        pdf.set_font("Helvetica","B",16)
        pdf.set_text_color(*GREEN)
        pdf.set_xy(10,7)
        pdf.cell(0,7,"DataJobs.Africa",ln=False)
        pdf.set_font("Helvetica","",8)
        pdf.set_text_color(180,220,180)
        pdf.set_xy(115,8)
        pdf.cell(0,5,"Dream Big, Think Sharp",ln=False)
        pdf.set_xy(115,14)
        pdf.set_font("Helvetica","",6.5)
        pdf.set_text_color(80,140,100)
        pdf.cell(0,4,"DATA  •  TECH  •  AI  •  AFRICA")

        # JOB ALERT badge
        pdf.set_xy(10,32)
        pdf.set_fill_color(*GREEN)
        pdf.set_font("Helvetica","B",9)
        pdf.set_text_color(*WHITE)
        pdf.cell(35,7,"  JOB ALERT",fill=True)

        # Title
        pdf.set_xy(10,43)
        pdf.set_font("Helvetica","B",13)
        pdf.set_text_color(*DARK)
        title = (job.get("title") or "N/A").upper()
        if len(title)>58: title=title[:56]+"…"
        pdf.cell(0,7,title)

        # Company
        pdf.set_xy(10,52)
        pdf.set_font("Helvetica","",10)
        pdf.set_text_color(*GREEN)
        pdf.cell(0,6,f"— {job.get('company','N/A')}")

        # Separator
        pdf.set_draw_color(*GREEN)
        pdf.set_line_width(0.4)
        pdf.line(10,61,200,61)

        # Fields
        fields = [
            ("Position",  (job.get("title") or "N/A")),
            ("Company",   job.get("company") or "N/A"),
            ("Location",  job.get("location") or job.get("country") or "N/A"),
            ("Type",      TYPE_LABELS.get(job.get("type",""), job.get("type","N/A"))),
            ("Level",     job.get("level") or "N/A"),
        ]
        dl = job.get("deadline","")
        fields.append(("Deadline", dl if dl and dl not in ["Not specified","Non spécifiée",""] else "Not specified"))
        sal = job.get("salary","")
        if sal and sal not in ["Not specified","Non spécifié",""]:
            fields.append(("Salary", sal))
        if job.get("remote"):
            fields.append(("Remote","Yes — Remote work available"))

        y = 65
        for lbl, val in fields:
            pdf.set_xy(10,y)
            pdf.set_font("Helvetica","B",8.5)
            pdf.set_text_color(*MUTED)
            pdf.cell(32,6,lbl+" :")
            pdf.set_font("Helvetica","",8.5)
            pdf.set_text_color(*DARK)
            v = str(val); v = v[:72]+"…" if len(v)>72 else v
            pdf.cell(0,6,v)
            pdf.set_draw_color(215,228,220)
            pdf.set_line_width(0.15)
            pdf.line(10,y+7,200,y+7)
            y += 8.5

        # Summary
        summary = job.get("summary","")
        if summary:
            y += 2
            pdf.set_xy(10,y)
            pdf.set_font("Helvetica","B",8.5)
            pdf.set_text_color(*MUTED)
            pdf.cell(0,6,"Summary :")
            y += 7
            pdf.set_xy(10,y)
            pdf.set_font("Helvetica","",8)
            pdf.set_text_color(*DARK)
            pdf.multi_cell(190,5,summary[:700]+("…" if len(summary)>700 else ""))
            y = pdf.get_y()+3

        # Apply links
        cur_y = pdf.get_y()+3
        if job.get("applyLink") or job.get("contactEmail") or job.get("instructions"):
            pdf.set_xy(10,cur_y)
            pdf.set_font("Helvetica","B",8.5)
            pdf.set_text_color(*GREEN)
            if job.get("applyLink"):
                pdf.set_xy(10,pdf.get_y())
                pdf.cell(0,6,f"Apply: {job['applyLink'][:80]}",ln=True)
            if job.get("contactEmail"):
                pdf.set_xy(10,pdf.get_y())
                pdf.cell(0,6,f"Email: {job['contactEmail']}",ln=True)
            if job.get("instructions"):
                pdf.set_xy(10,pdf.get_y())
                pdf.set_text_color(*DARK)
                pdf.cell(0,6,f"Instructions: {job['instructions'][:80]}",ln=True)

        # Footer band
        pdf.set_fill_color(*DARK)
        pdf.rect(0,272,210,25,style="F")
        pdf.set_fill_color(*GOLD)
        pdf.rect(0,272,210,1,style="F")

        # Social footer — order: Site, Facebook, LinkedIn, WhatsApp
        socials = [
            ("Site:",     SITE_URL),
            ("Facebook:", FACEBOOK_URL),
            ("LinkedIn:", "linkedin.com/in/datajobs-africa"),
            ("WhatsApp:", WHATSAPP_URL[:32] if len(WHATSAPP_URL)>32 else WHATSAPP_URL),
        ]
        cw = 52
        for i,(lbl,val) in enumerate(socials):
            fx = 4 + i*cw
            pdf.set_xy(fx,274)
            pdf.set_font("Helvetica","B",5.5)
            pdf.set_text_color(140,200,160)
            pdf.cell(cw-2,4,lbl)
            pdf.set_xy(fx,279)
            pdf.set_font("Helvetica","",5)
            pdf.set_text_color(*GREEN)
            short = val.replace("https://","").replace("http://","")
            short = short[:32]+"…" if len(short)>32 else short
            pdf.cell(cw-2,4,short)

        pdf.set_xy(10,288)
        pdf.set_font("Helvetica","I",6.5)
        pdf.set_text_color(70,130,90)
        pdf.cell(0,4,"Rejoignez la communaute des talents data, tech & AI en Afrique.")

    buf = io.BytesIO()
    pdf.output(buf)
    buf.seek(0)
    return buf, None

# ─────────────────────────────────────────────────
#  HTML TEMPLATE
# ─────────────────────────────────────────────────
HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>DataJobs Africa — Admin</title>
  <link href="https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=Space+Mono:wght@400;700&family=Inter:wght@300;400;500&display=swap" rel="stylesheet">
  <style>
    :root{--nav:#0d2b1f;--green:#00a86b;--gold:#ffb800;--bg:#f4f6f9;--card:#fff;--border:#dce4ec;--text:#1a2a32;--muted:#4a6272;--red:#e65c5c;--blue:#1a3a80;}
    *,*::before,*::after{box-sizing:border-box;margin:0;padding:0;}
    body{background:var(--bg);color:var(--text);font-family:'Inter',sans-serif;font-weight:300;min-height:100vh;}
    nav{background:var(--nav);border-bottom:3px solid var(--gold);padding:0 2rem;height:52px;display:flex;align-items:center;gap:1.5rem;position:sticky;top:0;z-index:100;}
    .nb{font-family:'Syne',sans-serif;font-weight:800;font-size:1.1rem;color:var(--green);text-decoration:none;}
    .nb span{color:#fff;}
    .ntabs{display:flex;gap:0;margin-left:.5rem;}
    .ntab{padding:.35rem .9rem;font-family:'Space Mono',monospace;font-size:.63rem;text-transform:uppercase;letter-spacing:.08em;color:#9ab8a0;text-decoration:none;border-bottom:2px solid transparent;transition:all .15s;}
    .ntab:hover,.ntab.active{color:var(--gold);border-bottom-color:var(--gold);}
    .nr{margin-left:auto;display:flex;align-items:center;gap:.7rem;}
    .badge{font-family:'Space Mono',monospace;font-size:.56rem;background:var(--gold);color:var(--nav);padding:.16rem .45rem;font-weight:700;}
    .container{max-width:1020px;margin:0 auto;padding:2rem 1.5rem;}
    .alert{padding:.72rem 1.1rem;margin-bottom:1.5rem;font-family:'Space Mono',monospace;font-size:.7rem;border-left:4px solid;}
    .alert-success{background:#d4edda;color:#1a5c2a;border-color:var(--green);}
    .alert-error{background:#f8d7da;color:#5c1a1a;border-color:var(--red);}
    /* FORM */
    .fcard{background:var(--card);border:1px solid var(--border);border-top:3px solid var(--gold);padding:2rem;}
    .ftitle{font-family:'Syne',sans-serif;font-weight:800;font-size:1.25rem;margin-bottom:1.6rem;}
    .g2{display:grid;grid-template-columns:1fr 1fr;gap:1rem;}
    .fg{margin-bottom:.9rem;}
    label{font-weight:500;font-size:.81rem;display:block;margin-bottom:.25rem;}
    .req{color:var(--red);}
    input[type=text],input[type=url],input[type=email],input[type=date],select,textarea{width:100%;padding:.52rem .75rem;border:1px solid var(--border);background:#fff;font-family:'Inter',sans-serif;font-size:.86rem;color:var(--text);outline:none;transition:border-color .15s;}
    input:focus,select:focus,textarea:focus{border-color:var(--green);}
    textarea{resize:vertical;min-height:72px;}
    .cb-row{display:flex;align-items:center;gap:.45rem;margin-top:.35rem;}
    .cb-row input{width:auto;}
    .cb-row label{margin:0;font-weight:300;}
    .hint{font-size:.68rem;color:var(--muted);margin-top:.2rem;font-style:italic;}
    .ghd{font-family:'Syne',sans-serif;font-weight:700;font-size:.73rem;color:var(--text);padding:.65rem 0 .2rem;text-transform:uppercase;letter-spacing:.04em;border-bottom:1px solid var(--border);margin-bottom:.3rem;}
    /* BUTTONS */
    .btn{display:inline-flex;align-items:center;gap:.4rem;padding:.52rem 1rem;font-family:'Space Mono',monospace;font-size:.66rem;font-weight:700;text-decoration:none;cursor:pointer;border:none;transition:all .15s;}
    .btn-green{background:var(--green);color:#000;}.btn-green:hover{background:#00c87a;}
    .btn-gold{background:var(--gold);color:var(--nav);}.btn-gold:hover{background:#ffc820;}
    .btn-red{background:var(--red);color:#fff;}.btn-red:hover{background:#c04040;}
    .btn-ghost{background:transparent;border:1px solid var(--border);color:var(--muted);}.btn-ghost:hover{border-color:var(--green);color:var(--green);}
    .btn-blue{background:var(--blue);color:#fff;}.btn-blue:hover{background:#1a4aaa;}
    .btn-sm{padding:.26rem .55rem;font-size:.58rem;}
    .fa{display:flex;gap:.65rem;flex-wrap:wrap;margin-top:1.4rem;padding-top:1.1rem;border-top:1px solid var(--border);}
    /* TABLE */
    .sh{display:flex;align-items:center;justify-content:space-between;margin-bottom:.9rem;flex-wrap:wrap;gap:.5rem;}
    .st{font-family:'Syne',sans-serif;font-weight:700;font-size:1.05rem;}
    .bulk{display:flex;align-items:center;gap:.45rem;flex-wrap:wrap;padding:.7rem;background:rgba(0,168,107,.06);border:1px solid rgba(0,168,107,.2);margin-bottom:.8rem;}
    .sal{display:flex;align-items:center;gap:.5rem;margin-bottom:.55rem;}
    .sal label{font-size:.78rem;color:var(--muted);}
    .tw{overflow-x:auto;border:1px solid var(--border);}
    table{width:100%;border-collapse:collapse;font-size:.77rem;}
    th{background:var(--nav);color:var(--gold);font-family:'Space Mono',monospace;font-size:.56rem;text-transform:uppercase;letter-spacing:.1em;padding:.62rem .75rem;text-align:left;white-space:nowrap;}
    td{padding:.58rem .75rem;border-bottom:1px solid #f0f4f8;vertical-align:middle;}
    tr:hover td{background:#f6f9fb;}
    .chip{display:inline-block;font-family:'Space Mono',monospace;font-size:.5rem;padding:.08rem .3rem;text-transform:uppercase;letter-spacing:.04em;font-weight:700;}
    .cg{background:rgba(0,168,107,.1);color:var(--green);}
    .cy{background:rgba(255,184,0,.13);color:#7a5a00;}
    .cr{background:rgba(230,92,92,.11);color:var(--red);}
    .cb2{background:rgba(26,58,128,.1);color:var(--blue);}
    .jck{accent-color:var(--green);width:15px;height:15px;cursor:pointer;}
    /* WA */
    .wap{background:#e8f5e9;border:1px solid #a5d6a7;padding:.9rem 1.1rem;font-family:monospace;font-size:.73rem;white-space:pre-wrap;line-height:1.6;max-height:300px;overflow-y:auto;margin-top:.7rem;}
    /* RESP */
    @media(max-width:620px){.g2{grid-template-columns:1fr;}.ntabs{display:none;}}
  </style>
</head>
<body>
<nav>
  <a href="/" class="nb">Data<span>Jobs</span>.Africa</a>
  <div class="ntabs">
    <a href="/" class="ntab {{ 'active' if page=='add' }}">➕ Add Job</a>
    <a href="/jobs" class="ntab {{ 'active' if page=='jobs' }}">📋 All Jobs ({{ total }})</a>
    <a href="/whatsapp" class="ntab {{ 'active' if page=='wa' }}">💬 WhatsApp</a>
    <a href="/push" class="ntab">🚀 GitHub</a>
  </div>
  <div class="nr"><span class="badge">{{ total }} Jobs</span></div>
</nav>

<div class="container">
{% if message %}
<div class="alert alert-{{ msg_type or 'success' }}">{{ message }}</div>
{% endif %}

{# ── ADD FORM ── #}
{% if page == 'add' %}
<div class="fcard">
  <div class="ftitle">📌 Add a New Job Offer</div>
  <form method="post" action="/">
    <div class="g2">
      <div class="fg"><label>Job Title <span class="req">*</span></label><input type="text" name="title" required placeholder="e.g. Data Scientist"></div>
      <div class="fg"><label>Company <span class="req">*</span></label><input type="text" name="company" required placeholder="e.g. World Bank"></div>
    </div>
    <div class="g2">
      <div class="fg">
        <label>Region <span class="req">*</span></label>
        <select name="region" required>
          <option value="">Select region</option>
          <option>North Africa</option><option>West Africa</option>
          <option>Central Africa</option><option>East Africa</option>
          <option>Southern Africa</option><option>Europe</option>
          <option>North America</option><option>International / Remote</option>
        </select>
      </div>
      <div class="fg"><label>Country</label><input type="text" name="country" placeholder="e.g. Cameroon"></div>
    </div>
    <div class="g2">
      <div class="fg"><label>City</label><input type="text" name="city" placeholder="e.g. Yaoundé, Nairobi"></div>
      <div class="fg">
        <label>Experience Level <span class="req">*</span></label>
        <select name="level" required>
          <option value="">Select</option>
          <option>Intern</option><option>Junior</option><option>Mid</option>
          <option>Senior</option><option>Lead</option><option>Director</option>
        </select>
      </div>
    </div>
    <div class="fg">
      <label>Job Type</label>
      <select name="type">
        {% for gname, gtypes in type_groups.items() %}
        <optgroup label="{{ gname }}">
          {% for k,v in gtypes.items() %}<option value="{{ k }}">{{ v }}</option>{% endfor %}
        </optgroup>
        {% endfor %}
      </select>
    </div>
    <div class="g2">
      <div class="fg">
        <label>Application Deadline</label>
        <input type="date" name="deadline" id="dlDate">
        <div class="cb-row"><input type="checkbox" id="dlNS" name="dlNotSpecified" onchange="document.getElementById('dlDate').disabled=this.checked"><label for="dlNS">Not specified</label></div>
      </div>
      <div class="fg"><label>Salary (optional)</label><input type="text" name="salary" placeholder="e.g. 2M–3M FCFA / $40k"></div>
    </div>
    <div class="g2">
      <div class="fg"><label>Contract / Duration</label><input type="text" name="duration" value="CDI" placeholder="CDI, CDD 2 years, Freelance"></div>
      <div class="fg" style="display:flex;align-items:flex-end;padding-bottom:.3rem;">
        <div class="cb-row"><input type="checkbox" name="remote" id="remCb"><label for="remCb">🌐 Remote / Work from home</label></div>
      </div>
    </div>
    <div class="fg"><label>Contact Email</label><input type="email" name="contactEmail" placeholder="recruitment@org.africa"><div class="hint">Blue clickable link on site</div></div>
    <div class="fg"><label>Application Link</label><input type="url" name="applyLink" placeholder="https://…"><div class="hint">Direct URL to apply</div></div>
    <div class="fg"><label>Application Instructions</label><textarea name="instructions" placeholder="e.g. Apply on company website / Send CV to…"></textarea></div>
    <div class="g2">
      <div class="fg"><label>PDF Link</label><input type="url" name="pdfLink" placeholder="https://…"></div>
      <div class="fg"><label>Full Job Posting Link</label><input type="url" name="fullJobPosting" placeholder="https://…"></div>
    </div>
    <div class="fa">
      <button type="submit" name="action" value="add" class="btn btn-green">➕ Add Job</button>
      <button type="submit" name="action" value="add_push" class="btn btn-gold">➕ Add + Push GitHub</button>
      <button type="submit" name="action" value="add_wa" class="btn btn-ghost">➕ Add + Preview WhatsApp</button>
    </div>
  </form>
  {% if wa_preview %}
  <div style="margin-top:1.4rem;">
    <div style="font-family:'Space Mono',monospace;font-size:.62rem;color:var(--muted);margin-bottom:.35rem;">WhatsApp preview:</div>
    <div class="wap" id="waP">{{ wa_preview }}</div>
    <button class="btn btn-ghost btn-sm" style="margin-top:.4rem;" onclick="cp('waP')">📋 Copy</button>
  </div>
  {% endif %}
</div>
{% endif %}

{# ── JOBS TABLE ── #}
{% if page == 'jobs' %}
<div class="sh">
  <div class="st">All Jobs ({{ total }})</div>
  <div style="display:flex; gap:0.5rem;">
    <a href="/" class="btn btn-green btn-sm">➕ Add New</a>
    <a href="/push" class="btn btn-gold btn-sm">🚀 Push to GitHub</a>
  </div>
</div>

<div class="sal">
  <input type="checkbox" id="sa" class="jck" onchange="toggleAll(this)">
  <label for="sa">Select all</label>
</div>

<div class="bulk" id="bulk" style="display:none;">
  <span style="font-family:'Space Mono',monospace;font-size:.63rem;color:var(--muted);" id="sc">0 selected</span>
  <button class="btn btn-blue btn-sm" onclick="genImgs()">🖼 Generate Images</button>
  <button class="btn btn-gold btn-sm" onclick="genPDF()">📄 Download PDF</button>
  <button class="btn btn-ghost btn-sm" onclick="clrSel()">✕ Clear</button>
</div>

<div id="imgSt" style="display:none;font-family:'Space Mono',monospace;font-size:.68rem;color:var(--green);margin-bottom:.7rem;"></div>

<div class="tw">
  <table>
    <thead>
      <tr><th>☑</th><th>#</th><th>Title</th><th>Company</th><th>Location</th><th>Type</th><th>Level</th><th>Deadline</th><th>Date</th><th>Actions</th></tr>
    </thead>
    <tbody>
      {% for j in jobs %}
      <tr>
        <td><input type="checkbox" class="jck jcb" data-id="{{ j.id }}" onchange="updBulk()"></td>
        <td style="font-family:'Space Mono',monospace;font-size:.56rem;color:var(--muted);">{{ loop.index }}</td>
        <td style="font-weight:500;max-width:175px;">{{ j.title }}</td>
        <td style="color:var(--muted);max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{{ j.company }}</td>
        <td style="font-size:.74rem;">{{ j.location or j.country or '—' }}</td>
        <td><span class="chip cg">{{ type_labels.get(j.type, j.type or '?') }}</span></td>
        <td><span class="chip cy">{{ j.level or '—' }}</span></td>
        <td style="font-family:'Space Mono',monospace;font-size:.6rem;">
          {% if j.deadline and j.deadline not in ['Not specified','Non spécifiée',''] %}{{ j.deadline }}{% else %}—{% endif %}
        </td>
        <td style="font-family:'Space Mono',monospace;font-size:.6rem;">{{ j.date or '—' }}</td>
        <td>
          <div style="display:flex;gap:3px;">
            <a href="/image/{{ j.id }}" class="btn btn-blue btn-sm" title="Image" target="_blank">🖼</a>
            <a href="/whatsapp/{{ j.id }}" class="btn btn-ghost btn-sm" title="WhatsApp">💬</a>
            <a href="/delete/{{ j.id }}" class="btn btn-red btn-sm" onclick="return confirm('Delete?')" title="Delete">🗑</a>
          </div>
        </td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% endif %}

{# ── WHATSAPP ALL ── #}
{% if page == 'wa' %}
<div class="sh">
  <div class="st">💬 WhatsApp Messages ({{ total }})</div>
  <a href="/whatsapp/all/download" class="btn btn-gold btn-sm">⬇ Download .txt</a>
</div>
{% for j,msg in wa_messages %}
<div style="margin-bottom:1.8rem;">
  <div style="font-family:'Syne',sans-serif;font-weight:700;font-size:.88rem;margin-bottom:.32rem;">{{ j.title }} — {{ j.company }}</div>
  <div class="wap" id="wa-{{ j.id }}">{{ msg }}</div>
  <button class="btn btn-ghost btn-sm" style="margin-top:.35rem;" onclick="cp('wa-{{ j.id }}')">📋 Copy</button>
</div>
{% endfor %}
{% endif %}

{# ── WHATSAPP SINGLE ── #}
{% if page == 'wa_single' %}
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem;">
  <div style="font-family:'Syne',sans-serif;font-weight:700;font-size:1rem;">💬 WhatsApp Message</div>
  <a href="/jobs" class="btn btn-ghost btn-sm">← All Jobs</a>
</div>
<div class="wap" id="waS">{{ wa_single }}</div>
<button class="btn btn-gold" style="margin-top:.55rem;" onclick="cp('waS')">📋 Copy</button>
{% endif %}

</div>

<script>
function cp(id){
  const el=document.getElementById(id);
  navigator.clipboard.writeText(el.textContent).then(()=>{
    const b=el.nextElementSibling;
    const o=b.textContent;b.textContent='✅ Copied!';
    setTimeout(()=>b.textContent=o,2000);
  });
}
function toggleAll(cb){
  document.querySelectorAll('.jcb').forEach(c=>c.checked=cb.checked);
  updBulk();
}
function updBulk(){
  const chk=document.querySelectorAll('.jcb:checked');
  const bulk=document.getElementById('bulk');
  const sc=document.getElementById('sc');
  if(chk.length>0){bulk.style.display='flex';sc.textContent=chk.length+' selected';}
  else bulk.style.display='none';
}
function clrSel(){
  document.querySelectorAll('.jcb').forEach(c=>c.checked=false);
  document.getElementById('sa').checked=false;
  updBulk();
}
function getIds(){return[...document.querySelectorAll('.jcb:checked')].map(c=>c.dataset.id);}

function genImgs(){
  const ids=getIds();
  if(!ids.length){alert('Select at least one job.');return;}
  const st=document.getElementById('imgSt');
  st.style.display='block';st.textContent='Generating images…';
  ids.forEach((id,i)=>{
    setTimeout(()=>{
      const a=document.createElement('a');
      a.href=`/image/${id}`;a.target='_blank';
      document.body.appendChild(a);a.click();document.body.removeChild(a);
      if(i===ids.length-1){
        st.textContent=`✅ ${ids.length} image(s) downloaded!`;
        setTimeout(()=>st.style.display='none',3000);
      }
    },i*900);
  });
}

function genPDF(){
  const ids=getIds();
  if(!ids.length){alert('Select at least one job.');return;}
  const st=document.getElementById('imgSt');
  st.style.display='block';st.textContent='Generating PDF…';
  const form=document.createElement('form');
  form.method='POST';form.action='/pdf';form.target='_blank';
  const inp=document.createElement('input');
  inp.type='hidden';inp.name='ids';inp.value=ids.join(',');
  form.appendChild(inp);document.body.appendChild(form);
  form.submit();document.body.removeChild(form);
  setTimeout(()=>st.style.display='none',3000);
}
</script>
</body>
</html>
"""

# ─────────────────────────────────────────────────
#  ROUTES
# ─────────────────────────────────────────────────
def render(page, jobs=None, message=None, msg_type="success", **kw):
    if jobs is None: jobs = load_jobs()
    return render_template_string(HTML,
        page=page, jobs=jobs, total=len(jobs),
        message=message, msg_type=msg_type,
        type_groups=TYPE_GROUPS, type_labels=TYPE_LABELS, **kw)

@app.route("/", methods=["GET","POST"])
def add_job():
    jobs = load_jobs()
    jobs, m = auto_maintain(jobs)
    if m: save_jobs(jobs)
    message, msg_type, wa_preview = None, "success", None

    if request.method == "POST":
        f = request.form
        action = f.get("action","add")
        city    = f.get("city","").strip()
        country = f.get("country","").strip()
        remote  = "remote" in f
        dl_ns   = "dlNotSpecified" in f

        if not country and not city and remote:
            location = country = "Global (Remote)"
        elif not country and city:
            location = city; country = "Global"
        else:
            location = ", ".join(filter(None,[city,country]))

        deadline = "Not specified" if dl_ns else (f.get("deadline","") or "Not specified")
        titre    = f.get("title","").strip()
        company  = f.get("company","").strip()

        summary = f"{titre} position at {company}."
        if location: summary += f" Based in {location}."
        if deadline not in ["Not specified",""]: summary += f" Apply before {deadline}."
        if remote: summary += " Remote work available."
        fp = f.get("fullJobPosting","").strip()
        if fp: summary += f" Full posting: {fp}"

        new_job = {
            "id":             int(datetime.datetime.now().timestamp()*1000),
            "title":          titre,
            "company":        company,
            "region":         f.get("region",""),
            "location":       location,
            "country":        country,
            "city":           city,
            "type":           f.get("type","data-science"),
            "level":          f.get("level",""),
            "deadline":       deadline,
            "salary":         f.get("salary","") or "Not specified",
            "duration":       f.get("duration","CDI") or "CDI",
            "remote":         remote,
            "isNew":          True,
            "expired":        False,
            "date":           datetime.datetime.now().strftime("%d/%m/%Y"),
            "description":    "",
            "contactEmail":   f.get("contactEmail","").strip(),
            "applyLink":      f.get("applyLink","").strip(),
            "instructions":   f.get("instructions","").strip(),
            "pdfLink":        f.get("pdfLink","").strip(),
            "fullJobPosting": fp,
            "source":         "admin_web",
            "summary":        summary,
        }
        jobs.insert(0, new_job)
        save_jobs(jobs)
        message = f"✅ Job added! ({len(jobs)} total)"
        if action == "add_push":
            r = github_push(f"feat: add '{titre}'")
            message += f" | {r['msg']}"
            if not r["success"]: msg_type = "error"
        if action == "add_wa":
            wa_preview = build_whatsapp(new_job)
            return render("add", jobs, message, msg_type, wa_preview=wa_preview)

    return render("add", jobs, message, msg_type, wa_preview=wa_preview)

@app.route("/jobs")
def list_jobs():
    jobs = load_jobs()
    jobs, m = auto_maintain(jobs)
    if m: save_jobs(jobs)
    return render("jobs", jobs)

@app.route("/delete/<int:jid>")
def delete_job(jid):
    jobs = [j for j in load_jobs() if j.get("id") != jid]
    save_jobs(jobs)
    return redirect(url_for("list_jobs"))

@app.route("/whatsapp")
def whatsapp_all():
    jobs = load_jobs()
    return render("wa", jobs, wa_messages=[(j,build_whatsapp(j)) for j in jobs])

@app.route("/whatsapp/<job_id>")
def whatsapp_single(job_id):
    jobs = load_jobs()
    job  = next((j for j in jobs if str(j.get("id"))==str(job_id)), None)
    if not job: return redirect(url_for("list_jobs"))
    return render("wa_single", jobs, wa_single=build_whatsapp(job))

@app.route("/whatsapp/all/download")
def whatsapp_download():
    content = "\n\n".join(build_whatsapp(j) for j in load_jobs())
    return Response(content, mimetype="text/plain",
        headers={"Content-Disposition":"attachment;filename=whatsapp_messages.txt"})

@app.route("/push")
def push_github():
    # On recharge et on sauvegarde explicitement avant le push
    jobs = load_jobs()
    save_jobs(jobs)
    
    # On lance le push avec le nombre exact d'offres dans le message
    r = github_push(f"chore: sync manual - {len(jobs)} offres")
    
    # On affiche le résultat sur la page de liste des jobs
    return render("jobs", jobs=jobs, message=r["msg"], msg_type="success" if r["success"] else "error")

@app.route("/image/<job_id>")
def image_single(job_id):
    jobs = load_jobs()
    job  = next((j for j in jobs if str(j.get("id"))==str(job_id)), None)
    if not job: return "Job not found", 404
    idx  = next((i for i,j in enumerate(jobs) if str(j.get("id"))==str(job_id)), 0)
    buf, err = generate_job_image(job, color_idx=idx)
    if err: return f"Error: {err}<br><code>pip install pillow</code>", 500
    name = f"DJA_{job.get('title','job').replace(' ','_')[:28]}.png"
    return send_file(buf, mimetype="image/png", as_attachment=True, download_name=name)

@app.route("/pdf", methods=["POST"])
def pdf_export():
    ids = set(request.form.get("ids","").split(","))
    if not ids: return "No jobs selected", 400
    jobs = load_jobs()
    sel  = [j for j in jobs if str(j.get("id")) in ids]
    if not sel: return "No matching jobs", 404
    buf, err = generate_pdf(sel)
    if err: return f"Error: {err}<br><code>pip install fpdf2</code>", 500
    name = f"DataJobsAfrica_{datetime.date.today()}.pdf"
    return send_file(buf, mimetype="application/pdf", as_attachment=True, download_name=name)

@app.route("/api/jobs")
def api_jobs():
    return jsonify(load_jobs())

# ─────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────
if __name__ == "__main__":
    print("="*55)
    print("  DataJobs Africa — Admin Panel")
    print("="*55)
    print(f"  📄 JSON   : {os.path.abspath(JSON_FILE)}")
    print(f"  🌍 Site   : {SITE_URL}")
    print(f"  🚀 GitHub : {'ENABLED' if GITHUB_ENABLED else 'DISABLED'}")
    print()
    print("  📦 Install: pip install flask pillow fpdf2")
    print()
    print("  👉 Open  : http://localhost:5000")
    print("  ❌ Stop  : Ctrl+C")
    print("="*55)
    app.run(debug=False, port=5000)
