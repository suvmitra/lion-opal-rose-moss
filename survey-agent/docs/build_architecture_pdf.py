#!/usr/bin/env python3
"""Generate Survey Agent architecture PDF for external expert review."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

OUT = Path(__file__).resolve().parent / "Survey_Agent_Architecture_v24.0.115.pdf"
NAVY = colors.HexColor("#0F2744")
TEAL = colors.HexColor("#0F6B5C")
AMBER = colors.HexColor("#B45309")
LIGHT = colors.HexColor("#F4F7FA")
RULE = colors.HexColor("#D6DEE8")
MUTED = colors.HexColor("#4B5563")


def styles():
    base = getSampleStyleSheet()
    s = {
        "cover_kicker": ParagraphStyle(
            "cover_kicker", parent=base["Normal"], fontName="Helvetica",
            fontSize=9, textColor=TEAL, tracking=1.2, spaceAfter=6,
        ),
        "cover_title": ParagraphStyle(
            "cover_title", parent=base["Title"], fontName="Helvetica-Bold",
            fontSize=22, leading=26, textColor=NAVY, alignment=TA_LEFT, spaceAfter=8,
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub", parent=base["Normal"], fontName="Helvetica",
            fontSize=11, leading=15, textColor=MUTED, spaceAfter=4,
        ),
        "h1": ParagraphStyle(
            "h1", parent=base["Heading1"], fontName="Helvetica-Bold",
            fontSize=14, leading=18, textColor=NAVY, spaceBefore=14, spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"], fontName="Helvetica-Bold",
            fontSize=11.5, leading=15, textColor=TEAL, spaceBefore=10, spaceAfter=5,
        ),
        "h3": ParagraphStyle(
            "h3", parent=base["Heading3"], fontName="Helvetica-Bold",
            fontSize=10.5, leading=13, textColor=NAVY, spaceBefore=8, spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "body", parent=base["Normal"], fontName="Helvetica",
            fontSize=9.2, leading=13, textColor=colors.HexColor("#1F2933"),
            alignment=TA_JUSTIFY, spaceAfter=6,
        ),
        "bullet": ParagraphStyle(
            "bullet", parent=base["Normal"], fontName="Helvetica",
            fontSize=9.2, leading=12.5, textColor=colors.HexColor("#1F2933"),
            leftIndent=12, spaceAfter=2,
        ),
        "code": ParagraphStyle(
            "code", parent=base["Code"], fontName="Courier",
            fontSize=7.4, leading=10, textColor=NAVY, backColor=LIGHT,
            leftIndent=4, rightIndent=4, spaceBefore=4, spaceAfter=8,
        ),
        "caption": ParagraphStyle(
            "caption", parent=base["Normal"], fontName="Helvetica-Oblique",
            fontSize=8, leading=11, textColor=MUTED, spaceAfter=8,
        ),
        "warn": ParagraphStyle(
            "warn", parent=base["Normal"], fontName="Helvetica",
            fontSize=9.2, leading=13, textColor=AMBER, spaceAfter=6,
        ),
        "th": ParagraphStyle(
            "th", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=8, leading=11, textColor=colors.white,
        ),
        "td": ParagraphStyle(
            "td", parent=base["Normal"], fontName="Helvetica",
            fontSize=8, leading=11, textColor=colors.HexColor("#1F2933"),
        ),
        "td_small": ParagraphStyle(
            "td_small", parent=base["Normal"], fontName="Helvetica",
            fontSize=7.4, leading=10, textColor=colors.HexColor("#1F2933"),
        ),
        "footer": ParagraphStyle(
            "footer", parent=base["Normal"], fontName="Helvetica",
            fontSize=7.5, textColor=MUTED,
        ),
    }
    return s


def header_footer(canvas, doc):
    canvas.saveState()
    w, h = A4
    canvas.setFillColor(NAVY)
    canvas.rect(0, h - 12 * mm, w, 12 * mm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(18 * mm, h - 7.5 * mm, "Survey Agent  ·  Architecture Brief  ·  v24.0.115")
    canvas.drawRightString(w - 18 * mm, h - 7.5 * mm, "Confidential — expert review")
    canvas.setFillColor(TEAL)
    canvas.rect(0, 0, w, 10 * mm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(18 * mm, 4 * mm, "lion-opal-rose-moss / survey-agent")
    canvas.drawRightString(w - 18 * mm, 4 * mm, f"Page {doc.page}")
    canvas.restoreState()


def tbl(s, rows, col_widths):
    data = []
    for i, row in enumerate(rows):
        sty = s["th"] if i == 0 else s["td"]
        data.append([Paragraph(str(c).replace("\n", "<br/>"), sty) for c in row])
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 1), (-1, -1), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.3, RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def bullets(s, items):
    flow = []
    for item in items:
        flow.append(Paragraph("•  " + item, s["bullet"]))
    flow.append(Spacer(1, 3))
    return flow


def build():
    s = styles()
    story = []
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # COVER
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph("TECHNICAL ARCHITECTURE BRIEF  ·  FOR EXTERNAL REVIEW", s["cover_kicker"]))
    story.append(Paragraph("Vision-led agentic survey automation<br/>on Android (TopSurveys / Qualtrics WebView)", s["cover_title"]))
    story.append(Paragraph(
        "Repository: github.com/suvmitra/lion-opal-rose-moss &nbsp;·&nbsp; "
        "Package: survey-agent &nbsp;·&nbsp; Engine version: <b>24.0.115</b>",
        s["cover_sub"],
    ))
    story.append(Paragraph(f"Document generated: {generated} &nbsp;·&nbsp; Status: working system, not a research prototype", s["cover_sub"]))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        "This document describes what the program is, how it is built, how a single "
        "agent step runs, how answers are chosen, how taps are grounded on a phone "
        "screenshot, where large language models are used (and where they are not), "
        "and the failure modes that still dominate live runs. It is written so an "
        "independent expert can recommend the next architectural refinement without "
        "having to reverse-engineer 15,700 lines of concatenated Python.",
        s["body"],
    ))

    story.append(Paragraph("1. Executive summary", s["h1"]))
    story.append(Paragraph(
        "The agent fills paid mobile surveys inside the TopSurveys Android app. "
        "The survey UI is a Qualtrics (or similar) form rendered in a WebView, "
        "inside Aloha/Chrome-like chrome, on a physical Samsung-class device "
        "driven over ADB. There is no official survey API. Perception is a "
        "screenshot + Tesseract OCR + UIAutomator node dump. Action is "
        "<font face='Courier'>adb shell input tap/swipe/text</font> and a "
        "WebView click injection.",
        s["body"],
    ))
    story.append(Paragraph(
        "Control is a deterministic router of specialised screen handlers, not "
        "an unconstrained LLM loop. Gemini (and optionally Salad-hosted Qwen-VL) "
        "are backups when local routers cannot classify the screen. A knowledge "
        "base and persona file supply declared facts (age 44, Male, Dublin, "
        "child_age 8, …). Missing personal facts can be typed on the operator "
        "terminal and persisted.",
        s["body"],
    ))
    for b in [
        "<b>Goal:</b> complete a survey as a consistent human persona, as fast as is reliable, without minimizing the app or tapping the Android nav bar.",
        "<b>Loop:</b> observe → classify phase → specialised router → inspect/critique → execute → verify postcondition → learn (RL / screen signature).",
        "<b>Hard constraint:</b> each engine part file ≤ 800 lines; loaded into one namespace by bootstrap.py.",
        "<b>Current version:</b> 24.0.115 (green Participate pill center, mindset critique, county Dublin-then-scroll).",
        "<b>Dominant live failure (as of 2026-09-21):</b> operator still launching v24.0.93 from <font face='Courier'>clinical_trials\\survey_automation</font> instead of this repo; OCR baseline y=899 mapped to native (718,2776) and was refused as the system nav.",
    ]:
        story.append(Paragraph("•  " + b, s["bullet"]))

    story.append(Paragraph("2. Problem the software is solving", s["h1"]))
    story.append(Paragraph(
        "Market-research surveys on this channel are multi-page Qualtrics instruments: "
        "radios, checkboxes, dropdowns, free text, ranking, Likert sliders, MaxDiff "
        "most/least columns, matrices, captchas, drag-and-drop, cookie overlays, "
        "and sticky Continue footers. The WebView does not expose a stable DOM to "
        "the automation host. UIAutomator XML is incomplete for Qualtrics widgets "
        "(editable=0 on many screens). Therefore the program treats the screenshot "
        "as the source of truth and accessibility nodes as a hint.",
        s["body"],
    ))
    story.append(Paragraph("In-scope", s["h2"]))
    for b in [
        "Pick a Featured Survey tile from the TopSurveys dashboard.",
        "Pass landing CTAs (Participate / Start!), cookie banners, I Agree.",
        "Answer questions using knowledge_base.json and persona_data.py.",
        "Ask the human on the terminal only when a personal fact is missing and inference is not allowed.",
        "Scroll until Continue/Next is visible; tap it once the answer is filled.",
        "Recover from validation banners, keyboards covering Continue, and unchanged screens.",
    ]:
        story.append(Paragraph("•  " + b, s["bullet"]))
    story.append(Paragraph("Out of scope / policy limits", s["h2"]))
    for b in [
        "No medical, legal, financial, credential, or security inference (restricted categories in the KB).",
        "Camera / microphone / location permissions default deny (PERMISSION_POLICY=safe_only).",
        "Document picker may only select AUTHORIZED_UPLOAD_FILE.",
        "Does not drive the survey vendor's website in a desktop browser; Android only.",
        "Does not claim 100% survey completion; MAX_AGENT_STEPS=200 and a stagnation halt exist.",
    ]:
        story.append(Paragraph("•  " + b, s["bullet"]))

    story.append(Paragraph("3. Runtime environment", s["h1"]))
    story.append(tbl(s, [
        ["Layer", "Choice", "Notes"],
        ["Host OS", "Windows 10/11 (operator)", "Developed and run under E:\\AIML\\dev\\lion-opal-rose-moss\\survey-agent"],
        ["Python", "3.12 venv", "Dependencies: opencv-python, pytesseract, pillow, imagehash, requests, python-dotenv"],
        ["Device", "Physical Android phone via USB", "Typical screenshot 1440×3088; ADB default C:\\adb\\adb.exe"],
        ["App under test", "topsurveys.paid.survey.money.cash", "Surveys render in a WebView (Qualtrics-like)"],
        ["OCR", "Tesseract", "Full-page + crop PSM 7; weak on white-on-orange and status-bar noise"],
        ["Local VLM", "Salad Cloud Qwen2.5-VL-7B (optional)", "Often 404/503; marked offline for the rest of the run"],
        ["Cloud VLM", "Gemini 3.5 Flash-Lite then 3.6 Flash", "OpenAI-compatible endpoint; hourly cap default $0.30"],
        ["Source of truth repo", "github.com/suvmitra/lion-opal-rose-moss", "Branch main; do not run the old clinical_trials copy"],
    ], [38 * mm, 52 * mm, 84 * mm]))
    story.append(Paragraph("Table 1. Deployment stack.", s["caption"]))

    story.append(Paragraph("4. Repository and load model", s["h1"]))
    story.append(Paragraph(
        "survey_with_salad.py is a 22-line entry point. It calls "
        "survey_engine.bootstrap.load_engine(globals()), which exec's every "
        "file in survey_engine/parts/ in numeric order into one shared namespace. "
        "There are no circular imports because there are no intra-package imports: "
        "later files simply call functions defined earlier. bootstrap refuses to "
        "load a part that exceeds 800 lines.",
        s["body"],
    ))
    story.append(Preformatted(
        "survey-agent/\n"
        "  survey_with_salad.py          # entry: load_engine + main()\n"
        "  human_answer_matching.py      # terminal option matching\n"
        "  knowledge_base.json           # declared facts + RL policy blob\n"
        "  persona_data.py               # richer persona narrative\n"
        "  survey_engine/\n"
        "    bootstrap.py                # concat parts into one namespace\n"
        "    parts/00_config.py … 26_reason.py\n"
        "  archive/                      # monolith snapshots v24.0.16–0.87\n"
        "  fixtures/                     # regression screenshots",
        s["code"],
    ))

    story.append(Paragraph("5. Module map (parts)", s["h1"]))
    story.append(tbl(s, [
        ["Part", "Lines", "Responsibility"],
        ["00_config", "129", "VERSION, env, paths, logger, ADB/Tesseract/Gemini/Salad knobs"],
        ["01_changelog", "624", "Per-version change bullets used at startup"],
        ["02_runtime", "505", "Observation/ActionResult, fresh-run cleanup, ADB, screenshot, OCR, UI dump"],
        ["03_labels", "483", "CTA lexicons, landing/consent/dashboard detectors"],
        ["04_rank_likert", "530", "Ranking, Likert, classify_screen_phase"],
        ["05_kb_match", "651", "Tiles, option matching, KB load/write"],
        ["06_learning", "765", "Lessons, learned-screen signatures, tabular RL"],
        ["07_vlm", "793", "Salad + Gemini vision, stagnation VLM, failed-tap memory"],
        ["08_landing", "792", "milli→native, Participate/Start, I Agree, orange/green CTA, terminal close"],
        ["09_county", "720", "Irish county list: Dublin from KB, orange row, footer Continue"],
        ["10_children", "437", "Children count radios + child_age text"],
        ["11_carousel", "480", "Horizontal carousel rows"],
        ["12_maxdiff_selectall", "635", "MaxDiff most/least + select-all checklists"],
        ["13_select_one", "269", "Single-choice radios + select_then_continue"],
        ["14_matrix", "725", "Matrix grids, visual_progression_coords"],
        ["15_progression", "550", "Continue/Next, prefer_progression_over_repeat"],
        ["16_inspect", "800", "Last-chance inspector (gender, county, banners) + critique hook"],
        ["17_human", "562", "Terminal key-in; writes KB"],
        ["18–23 checks", "~2.4k", "Regression self-checks (dashboard, county, age, RL, MaxDiff, …)"],
        ["20_text_fields / 21_open_text", "1.0k", "Age/postcode geometry, captcha, drag-drop, comments"],
        ["22_execute", "777", "Tap/type/scroll, SAFE TAP, postcondition verify"],
        ["24_preflight", "366", "Runs self-checks then Salad/Gemini/device probes"],
        ["25_runner", "800", "observe() + main() agent loop"],
        ["26_reason", "258", "Mindset prompt, green_cta_milli, critique_decision, THINK/VLM"],
    ], [38 * mm, 22 * mm, 114 * mm]))
    story.append(Paragraph("Table 2. Engine parts. Total ~15,768 lines including the entry file.", s["caption"]))

    story.append(Paragraph("6. The agent loop", s["h1"]))
    story.append(Paragraph(
        "main() in 25_runner.py is a bounded for-loop (default 200 steps). "
        "Each step is one Observe–Decide–Inspect–Act–Verify cycle. "
        "initialize_fresh_run() deletes screenshots, truncates debug_runner.log "
        "and automation_log.csv, and resets agent_state.json. Persistent "
        "knowledge_base.json is retained.",
        s["body"],
    ))
    story.append(Paragraph("6.1 Observe", s["h2"]))
    for b in [
        "ensure_survey_foreground() — relaunch TopSurveys if the app was sent home.",
        "capture_screenshot() — PNG + sha256 + perceptual hash; identical phash reuses the previous file.",
        "ocr() — Tesseract on the full screenshot.",
        "dump_ui_nodes() — UIAutomator dump; often 0 editable nodes on Qualtrics pages.",
        "classify_screen_phase() — dashboard | consent_overlay | survey_landing | survey_question | permission_dialog | document_picker | loading | completion | terminal_modal | navigation.",
        "Specialist detectors can force phase=survey_question (MaxDiff, matrix, children, county, …).",
        "load_kb() always; load_persona() on survey_question.",
    ]:
        story.append(Paragraph("•  " + b, s["bullet"]))

    story.append(Paragraph("6.2 Decide (router priority)", s["h2"]))
    story.append(Paragraph(
        "Hard routes run first so a specialised screen cannot be stolen by RL or Gemini:",
        s["body"],
    ))
    story.append(Preformatted(
        "1. I Agree / Decline consent\n"
        "2. Gender cards (Are you? Male/Female)\n"
        "3. Adult age text box (KB age=44)\n"
        "4. If screen unchanged N times → stagnation_gate → Gemini snapshot JSON\n"
        "5. Widget specialists (order matters):\n"
        "     close-confirm, Likert, ranking, drag-drop, captcha, select-all,\n"
        "     I Agree, select-one, open text, county list, children, child ages,\n"
        "     carousel, MaxDiff, occupation group, matrix\n"
        "6. Phase specialists: dashboard tile, permission, picker, cookie overlay,\n"
        "     landing Participate/Start\n"
        "7. On survey_question leftover:\n"
        "     lessons → RL replay → generalized_unseen_router → exact KB option →\n"
        "     declared preference → inferred preference → text KB → human prompt →\n"
        "     learned-screen action → Gemini observation prompt\n"
        "8. Post-decision repairs: text payload copy, human if empty personal,\n"
        "     authorized fallback, prefer_progression_over_repeat, inspect_decision\n"
        "     (which calls critique_decision), payload-None guard on select-one",
        s["code"],
    ))

    story.append(Paragraph("6.3 Act and verify", s["h2"]))
    story.append(Paragraph(
        "execute_action() maps milli coordinates [0–1000] to device pixels, "
        "refuses or clamps taps that would hit the Android navigation bar, "
        "types via keyevents or ADB text, scrolls with a swipe (list_scroll "
        "uses a shorter inner-list swipe). After the action, observe(light) "
        "and verify_postcondition() check hashes, OCR, orange/green bars, "
        "and widget-specific predicates (e.g. county list still open after "
        "tapping Dublin is success, not failure).",
        s["body"],
    ))
    story.append(Paragraph(
        "Reward is written into a small tabular RL store in knowledge_base.json "
        "and a per-signature learned_screen_actions table. Failures go to "
        "_FAILED_TAPS so the next loop must not repeat the same (x,y).",
        s["body"],
    ))

    story.append(Paragraph("7. Coordinate system (critical)", s["h1"]))
    story.append(Paragraph(
        "All decisions speak milli-coordinates: integers 0–1000 on each axis "
        "of the screenshot. Execution converts with normalized_to_native():",
        s["body"],
    ))
    story.append(Preformatted(
        "sx = image_width  * x / 1000\n"
        "sy = image_height * y / 1000\n"
        "if device_size != image_size:\n"
        "    sx *= device_width  / image_width\n"
        "    sy *= device_height / image_height",
        s["code"],
    ))
    story.append(Paragraph(
        "On the operator phone a screenshot is typically 1440×3088 and includes "
        "the status bar and the Android 3-button nav. That means:",
        s["body"],
    ))
    story.append(tbl(s, [
        ["Milli y", "Approx. native y (3088)", "What lives there"],
        ["0–80", "0–247", "Status bar / Aloha X and title"],
        ["280–520", "864–1605", "Question body, gender cards, age field, county rows"],
        ["770–875", "2378–2702", "In-content Continue / selected list row (Wexford, Kerry)"],
        ["850–875", "2625–2702", "Intended Participate / footer Continue CENTER"],
        ["890–920", "2748–2841", "OCR text baseline of a bottom pill; often the nav"],
        [">940", ">2902", "Android system nav — SAFE TAP must never land here"],
    ], [32 * mm, 52 * mm, 90 * mm]))
    story.append(Paragraph("Table 3. Empirical y-bands on a 1440×3088 screenshot.", s["caption"]))
    story.append(Paragraph(
        "Grounding methods, in intended order of trust: (1) HSV blob of the "
        "actual coloured control — orange_cta_milli for Qualtrics Continue, "
        "green_cta_milli for Participate (v24.0.115); (2) crop OCR of a known "
        "label; (3) accessibility node bounds, after discarding nav-bar and "
        "chrome nodes; (4) geometric fallbacks such as [500,860]. "
        "Tesseract's word box is the baseline of the glyphs, which sits below "
        "the visual centre of a pill. That single fact caused the 20+ iteration "
        "Participate stall: OCR y=899 → native 2776 → SAFE TAP refuse → Gemini "
        "repeats 900 → local router overwrites back to 899.",
        s["body"],
    ))

    story.append(Paragraph("8. Perception stack", s["h1"]))
    story.append(tbl(s, [
        ["Signal", "Producer", "Used for", "Failure mode"],
        ["PNG screenshot", "ADB screencap", "VLM, HSV, OCR, phash", "Dedup can hide a small orange change"],
        ["phash", "imagehash", "stagnation, screenshot reuse", "Wexford gray↔orange can still 'change'"],
        ["OCR text", "Tesseract", "phase, question, options", "Misses white-on-orange 'Dublin'; reads status bar"],
        ["UIAutomator XML", "uiautomator dump", "clickable nodes, bounds", "Qualtrics fields often absent / y=92% chrome"],
        ["HSV orange", "OpenCV inRange H 5–25", "Continue footer vs selected row", "Selected county row is also orange"],
        ["HSV green", "OpenCV H 35–95 (v115)", "Participate / Start pill centre", "Needs live screenshot; tests have none"],
        ["Crop OCR PSM 7", "Tesseract on ROI", "age digits in the box", "Red 'no more than 99' banner leaked as 99"],
    ], [32 * mm, 38 * mm, 50 * mm, 54 * mm]))
    story.append(Paragraph("Table 4. Sensors. Screenshot is authoritative; XML is a hint.", s["caption"]))

    story.append(Paragraph("9. Language models — where they sit", s["h1"]))
    story.append(Paragraph(
        "The design intent is: local geometry and the knowledge base answer "
        "known screens; the VLM is asked only when the router has no specialist "
        "or the screen is stagnating. In practice Gemini is still invoked too "
        "often because (a) Salad is frequently offline, (b) stagnation fires "
        "after 1–4 unchanged cycles, (c) inspect/landing routers overwrite the "
        "VLM JSON with the same OCR coordinate that already failed.",
        s["body"],
    ))
    story.append(tbl(s, [
        ["Role", "Model / stack", "When used"],
        ["Primary VLM (config)", "Salad Qwen2.5-VL-7B via SALAD_URL", "If preflight 200; else marked offline for the run"],
        ["Fallback VLM", "gemini-3.5-flash-lite then gemini-3.6-flash", "Observation prompt + stagnation JSON"],
        ["Prompt wrapper", "build_observation_prompt + mindset_prompt + ASK=", "Phase task, OCR, compact UI, KB/persona"],
        ["Stagnation JSON", "stagnation_vlm_decision", "Unchanged screen; must not reuse failed coords"],
        ["Age THINK", "think_from_screenshot", "Read digits in the age box when Tesseract is wrong"],
        ["Not used as planner", "—", "No multi-step tool-calling agent; one JSON action per call"],
    ], [40 * mm, 62 * mm, 72 * mm]))
    story.append(Paragraph("Table 5. Model usage. Hourly spend cap VLM_HOURLY_BUDGET_USD (default 0.30).", s["caption"]))
    story.append(Paragraph(
        "VLM_PRIMARY defaults to salad. If Salad returns 404/503, mark_salad_offline() "
        "stops retrying Salad for the rest of the process. Gemini stays in use. "
        "The operator is not currently blocked when Salad is down, by design.",
        s["body"],
    ))

    story.append(Paragraph("10. Knowledge, persona, and human input", s["h1"]))
    story.append(Paragraph(
        "knowledge_base.json holds declared facts the agent is allowed to type "
        "or tap without asking. persona_data.py is a richer narrative used as "
        "secondary evidence. Writes go back to the JSON with provenance "
        "(declared | inferred | human) and a confidence.",
        s["body"],
    ))
    story.append(tbl(s, [
        ["kb_key", "Value", "Typical widget"],
        ["age", "44", "Text box + Continue"],
        ["gender", "Male", "Cards or radios, then Continue"],
        ["city / county", "Dublin", "Open list, tap row, scroll to footer Continue"],
        ["area_code / postal_code", "D22 / D22V048", "Text"],
        ["child_age / number_of_children", "8 / 1", "Text / radio"],
        ["employment_status", "Employed Full-Time", "Select-one"],
        ["smoking_status", "No, I don't smoke", "Select-one"],
        ["household_pets", "Cat(s), Dog(s), Fish", "Multi-select"],
        ["seniority / occupation", "Senior Lead / middle manager", "Occupational group list"],
    ], [50 * mm, 55 * mm, 69 * mm]))
    story.append(Paragraph("Table 6. Core declared facts (see knowledge_base.json).", s["caption"]))
    story.append(Paragraph(
        "If a question is classified personal, the KB/persona miss, and inference "
        "is forbidden or low-confidence, capture_human_answer_decision() prints "
        "the question and visible options on the terminal. The operator may type "
        "labels ('Dublin'), indices ('3'), or 'skip'. Matching lives in "
        "human_answer_matching.py. A previous bug treated instructional paragraphs "
        "as options; matching now prefers numbered real choices and can accept "
        "'option 3' / 'middle manager'.",
        s["body"],
    ))

    story.append(Paragraph("11. Widget specialists", s["h1"]))
    story.append(tbl(s, [
        ["Widget", "Strategy", "Continue rule"],
        ["Select-one", "KB/persona/inference → tap radio (payload required)", "select_then_continue or later survey_next"],
        ["Multi-select", "Tap remaining KB items; do not toggle off", "When remaining=[]"],
        ["Gender cards", "Male at ~[280,280]; Continue ~[500,455]", "Never re-tap Male (deselects)"],
        ["Age text", "Field ~55 milli above orange Continue; type 44 once", "Dismiss keyboard, Continue; never 4444"],
        ["County list", "Open if closed; tap Dublin; orange between Donegal & Galway", "Only footer y≥860; else scroll_down only"],
        ["Children / ages", "KB number_of_children / child_age=8", "Type then Continue; do not prompt if KB has 8"],
        ["Ranking", "Tap remaining gray bars to assign 1..n", "All items teal before Continue"],
        ["Likert", "Named scale → 3/4/5; teal handle = filled", "No leftover up-arrow"],
        ["MaxDiff", "Most Important cell then Least Important cell", "Then scroll/Continue"],
        ["Select-all / claims", "Check KB-relevant boxes, skip Other", "Footer Continue after min checks"],
        ["Matrix", "Row×column from persona; one cell per row", "Scroll until Continue"],
        ["Open text", "≥5-word human-like sentence, not 'AI generated'", "Hide keyboard, Continue once"],
        ["Captcha", "Type on-screen distorted code", "Next, not Continue"],
        ["Drag-drop", "Long-press tile, drop on dashed target", "Then Next"],
        ["Landing", "green_cta_milli centre, WebView click", "Must not hit nav y>0.92"],
    ], [36 * mm, 78 * mm, 60 * mm]))
    story.append(Paragraph("Table 7. Specialist policies. Each has a session flag to prevent toggle/duplicate type.", s["caption"]))

    story.append(Paragraph("12. Learning mechanisms", s["h1"]))
    story.append(Paragraph(
        "Three overlapping memories exist. They have helped on repeated screens "
        "and also caused regressions when a coordinate was rewarded for the wrong "
        "reason (e.g. tapping Wexford y=780 'changed' the screenshot because the "
        "row toggled orange, RL q rose, later replay hit Wexford instead of Continue).",
        s["body"],
    ))
    for b in [
        "<b>learned_screen_actions</b> — signature from OCR keywords; reuse action if confidence ≥ LEARNED_ACTION_MIN_CONFIDENCE (0.80).",
        "<b>rl_policy</b> in knowledge_base.json — state = widget|question-stem, action_id = action|payload, tabular Q with n.",
        "<b>lessons / improve_survey_intelligence</b> — success/failure counters per semantic key.",
        "<b>generalized_unseen_router</b> — assume select-one / text / continue from visible controls when no specialist fires.",
        "Session flags (_COUNTY_SESSION, _AGE_SESSION, _I_AGREE_SESSION, …) are process-local and reset on fresh run; they must not leak across self-checks.",
    ]:
        story.append(Paragraph("•  " + b, s["bullet"]))

    story.append(Paragraph("13. Mindset critique (v24.0.114+)", s["h1"]))
    story.append(Paragraph(
        "The operator asked that curiosity, rationality, open-mindedness, "
        "objectivity, empiricism, critical thinking, skepticism and intellectual "
        "honesty be implemented as behaviour, not slogans. 26_reason.py does this:",
        s["body"],
    ))
    story.append(tbl(s, [
        ["Trait", "Code behaviour"],
        ["Curiosity", "Log SEE= first 120 OCR chars before every inspect"],
        ["Rationality", "If landing shows Participate, force that CTA"],
        ["Open-mind", "If (x,y) is in failed_coords_set, retry y-40"],
        ["Objectivity", "Prefer green HSV blob over remembered/OCR y"],
        ["Empiricism", "Unchanged phash ⇒ last tap missed; do not repeat it"],
        ["Critical thinking", "Is Continue/Participate actually on this screenshot?"],
        ["Skepticism", "y≥880 Participate → clamp 860; y≥940 is Android nav"],
        ["Honesty", "Continue with payload=None on a radio page is rejected; fill first"],
    ], [42 * mm, 132 * mm]))
    story.append(Paragraph("Table 8. Mindset is executed in critique_decision(), called from inspect_decision().", s["caption"]))
    story.append(Paragraph(
        "mindset_prompt() is also prepended to Gemini observation and stagnation "
        "prompts so the image model is asked to apply the same rules.",
        s["body"],
    ))

    story.append(Paragraph("14. Execution safety", s["h1"]))
    for b in [
        "SAFE TAP: native y ≥ nav_ratio×height is refused, except Participate which is clamped to 0.860×height and WebView-clicked.",
        "Forbidden targets: privacy-policy footer, Android recents/home/back, cookie 'X' when a real CTA exists, instruction paragraphs.",
        "prefer_progression_over_repeat: if Male (or any option) was already issued, do not tap it again (Qualtrics toggles cards off).",
        "Foreground watchdog: if TopSurveys is not resumed, relaunch the activity (a nav-bar miss sends the app home).",
        "Postcondition examples: 'screen changed', 'selected option is Dublin', 'field contains 44', 'maxdiff most selected'.",
    ]:
        story.append(Paragraph("•  " + b, s["bullet"]))

    story.append(Paragraph("15. Quality gates", s["h1"]))
    story.append(Paragraph(
        "preflight() runs a battery of Observation-built self-checks before ADB "
        "or Gemini are used in anger. A failed check aborts the process with a "
        "diff of expected vs actual decision dicts. That is why many operator "
        "logs start with a wall of [SELF-CHECK] lines — those are not live taps.",
        s["body"],
    ))
    for b in [
        "Dashboard tile selection, cookie overlay, Participate landing, Start! vs Continue.",
        "I Agree then orange Continue (not nav-bar).",
        "Postcode D22, smoking, pets multi-select, gender Continue, age 44 payload repair.",
        "County Dublin-not-Donegal, open-list tap, past-list scroll_up only before Dublin is chosen.",
        "RL select_one replay, MaxDiff most then least then Continue, ranking, Likert.",
        "Mindset: Participate y=899 clamped into 850–875.",
        "Then: Salad probe, Gemini probe, adb devices.",
    ]:
        story.append(Paragraph("•  " + b, s["bullet"]))

    story.append(Paragraph("16. Known failure modes (honest)", s["h1"]))
    story.append(Paragraph(
        "The system is a growing collection of geometric specialists around a "
        "screenshot. It is not yet a general GUI agent. The following are the "
        "failures an external reviewer should treat as first-class, not as "
        "one-off bugs.",
        s["body"],
    ))
    story.append(tbl(s, [
        ["ID", "Symptom", "Structural cause", "Current mitigation"],
        ["F1", "20+ loops on Participate", "OCR baseline ≠ pill centre; SAFE TAP refuse; VLM overwritten", "green_cta_milli + clamp (115). Operator must run this repo."],
        ["F2", "Male selected then unselected", "Second tap toggles Qualtrics card", "prefer_progression_over_repeat; gender session"],
        ["F3", "Age 4444 / banner 99", "Type twice; crop OCR reads error", "typed flag, crop ignore banner, THINK"],
        ["F4", "County Kerry/Wexford as Continue", "Any orange row treated as CTA; y=780", "Lowest orange y≥860 only; Dublin alignment"],
        ["F5", "County up/down oscillation", "OCR misses white-on-orange Dublin", "tapped/picked ⇒ scroll_down only"],
        ["F6", "Continue while unanswered", "Progression repair too eager", "required_answer_missing veto"],
        ["F7", "Human prompt storm", "Inspector reprints missing_fact_key", "Once per fact key; reload KB from disk"],
        ["F8", "Wrong folder / old version", "Two checkouts; screenshots path in clinical_trials", "Log CODE DIR; this PDF"],
        ["F9", "RL false-positive reward", "Toggle changes phash, q↑", "Do not replay y<860 on county lists"],
        ["F10", "Gemini cost / latency", "Stagnation VLM every unchanged cycle", "Need: stop calling VLM with the same failed coord"],
        ["F11", "Salad 404/503", "Container not up", "Offline for run; Gemini continues"],
        ["F12", "Module split at 800 lines", "inspect/runner/vlm at the cap", "Hard to add logic without deleting lines"],
    ], [16 * mm, 38 * mm, 58 * mm, 62 * mm]))
    story.append(Paragraph("Table 9. Reviewer punch-list. F1 and F8 are operational; F10 is architectural.", s["caption"]))

    story.append(Paragraph("17. Decision object (contract)", s["h1"]))
    story.append(Preformatted(
        "{\n"
        '  "screen_state": "survey_question|survey_landing|dashboard|...",\n'
        '  "question_text": str,\n'
        '  "action": "click|select_option|select_then_continue|type_text|\\n'
        '            scroll_down|scroll_up|wait|finish|request_human|...",\n'
        '  "target_element_id": int|None,     # UIAutomator node id\n'
        '  "target_text": str|None,           # label to tap or type\n'
        '  "target_coords": [x_milli, y_milli],\n'
        '  "coordinate_authoritative": bool,  # screenshot beat the node\n'
        '  "input_payload": str|None,         # must be set for radios/text\n'
        '  "kb_key": str|None, "kb_write": bool,\n'
        '  "confidence_score": 0..1,\n'
        '  "postcondition": "screen changed|selected option is Dublin|...",\n'
        '  "answer_reason": str, "visual_reasoning": str,\n'
        '  "answer_provenance": "verified|declared|inferred|human"\n'
        "}",
        s["code"],
    ))

    story.append(Paragraph("18. How to run (operator)", s["h1"]))
    story.append(Preformatted(
        "cd E:\\AIML\\dev\\lion-opal-rose-moss\n"
        "git pull origin main\n"
        "cd survey-agent\n"
        "# .venv already created; .env holds GEMINI_API_KEY, optional SALAD_*, ADB_PATH\n"
        "python survey_with_salad.py\n"
        "\n"
        "First log lines MUST contain:\n"
        "  FRESH SURVEY AUTOMATION SESSION - v24.0.115\n"
        "  CODE DIR=...\\lion-opal-rose-moss\\survey-agent\n"
        "If you see v24.0.93 or clinical_trials\\survey_automation you are on the old copy.",
        s["code"],
    ))
    story.append(Paragraph(
        "Artifacts per run: screenshots/step_NNNN.png, _verify_*.png, "
        "debug_runner.log, automation_log.csv, agent_state.json. "
        "knowledge_base.json is the only file intended to accumulate across runs.",
        s["body"],
    ))

    story.append(Paragraph("19. Questions for the consultant", s["h1"]))
    story.append(Paragraph(
        "The operator will use your recommendations for the next refinement. "
        "Please be opinionated on the following.",
        s["body"],
    ))
    story.append(Paragraph("Architecture", s["h2"]))
    for b in [
        "Should the 27-file exec-into-one-namespace model be replaced by a real package with typed interfaces, even if files stay small?",
        "Is a general GUI agent (screenshot → VLM → grounded SAM/UI-TARS/OmniParser boxes) a better backbone than per-widget routers, given the $0.30/hour cap?",
        "How should perception be unified: AccessibilityNode + screenshot crop embeddings + a single 'control detector' instead of orange HSV, green HSV, OCR, and XML fighting?",
        "What is the right coordinate frame — screenshot milli, dp, or a nav-bar-subtracted content box?",
    ]:
        story.append(Paragraph("•  " + b, s["bullet"]))
    story.append(Paragraph("Control and learning", s["h2"]))
    for b in [
        "The inspect + prefer_progression + RL replay stack often undoes a correct specialist. Propose a single authority (policy head) with explicit vetoes.",
        "Tabular RL rewarded a toggle as success. What learning signal is safe on a GUI where many taps are reversible?",
        "Stagnation currently re-asks Gemini every cycle. Propose a budgeted planner: one VLM sketch per unique phash, then only local retries.",
    ]:
        story.append(Paragraph("•  " + b, s["bullet"]))
    story.append(Paragraph("Reliability", s["h2"]))
    for b in [
        "How would you test this without a phone — screenshot replay, recorded ADB, or a Qualtrics fixture app?",
        "What SLOs are reasonable (median seconds per question, Continue success rate, Gemini $ / survey)?",
        "Is human-in-the-loop on the terminal acceptable in production, or should missing facts be collected in a pre-survey interview?",
    ]:
        story.append(Paragraph("•  " + b, s["bullet"]))

    story.append(Paragraph("20. Version lineage (selected)", s["h1"]))
    story.append(Paragraph(
        "The product evolved by live-screenshot patches, v24.0.16 through v24.0.115. "
        "Monolith snapshots live in archive/ up to 0.87; after that the engine is split. "
        "Highlights a reviewer may care about:",
        s["body"],
    ))
    story.append(tbl(s, [
        ["Ver", "Theme"],
        ["0.93", "I Agree OCR; TypeError int(list) on Continue coords — this is the copy still running in clinical_trials"],
        ["0.98–0.99", "Gender cards: tap Male once, then mid-screen Continue"],
        ["0.100–0.106", "Age 44 once, not 4444; field above Continue; keyboard dismiss"],
        ["0.107–0.112", "County: Dublin orange, never Kerry/Wexford as Continue; scroll down only after pick"],
        ["0.113–0.115", "Participate pill centre, SAFE TAP clamp, mindset critique, green HSV blob, CODE DIR log"],
    ], [28 * mm, 146 * mm]))
    story.append(Paragraph("Table 10. Recent versions. Always confirm the live log header, not git describe on another folder.", s["caption"]))

    story.append(Paragraph("21. Appendix — important environment variables", s["h1"]))
    story.append(tbl(s, [
        ["Variable", "Default", "Meaning"],
        ["ADB_PATH / DEVICE_ID", "C:\\adb\\adb.exe / first device", "Phone bridge"],
        ["TESSERACT_CMD", "C:\\Program Files\\Tesseract-OCR\\tesseract.exe", "OCR binary"],
        ["GEMINI_API_KEY", "(required if Salad down)", "Google AI Studio key"],
        ["SALAD_URL / SALAD_API_KEY", "empty", "Optional local VL"],
        ["VLM_PRIMARY", "salad", "salad | gemini"],
        ["VLM_HOURLY_BUDGET_USD", "0.30", "Hard-ish spend cap"],
        ["MAX_AGENT_STEPS", "200", "Loop ceiling"],
        ["MAX_STAGNATION_CYCLES", "4", "Unchanged-screen halt"],
        ["ALLOW_INTERACTIVE_HUMAN_INPUT", "true", "Terminal prompts"],
        ["ALLOW_PERSONAL_INFERENCE", "true", "Non-restricted guesses"],
        ["SURVEY_SELECTION_POLICY", "highest_value", "Dashboard tile pick"],
        ["COOKIE_CONSENT_ACTION", "accept", "accept | reject"],
        ["PERMISSION_POLICY", "safe_only", "Android permission dialogs"],
        ["KB_FILE / PERSONA_FILE", "next to the entry script", "Facts"],
    ], [58 * mm, 52 * mm, 64 * mm]))
    story.append(Paragraph("Table 11. Configuration. Loaded from survey-agent/.env.", s["caption"]))

    story.append(Paragraph("22. Appendix — one-step sequence diagram (textual)", s["h1"]))
    story.append(Preformatted(
        "Phone --screencap/ocr/dump--> observe()\n"
        "observe() --> classify_screen_phase + load_kb\n"
        "         --> specialist routers (priority list §6.2)\n"
        "         --> optional Gemini JSON if none / stagnating\n"
        "         --> repairs + inspect_decision\n"
        "                 \\--> critique_decision (mindset, green blob, failed coords)\n"
        "         --> execute_action (milli→native, SAFE TAP, webview or adb)\n"
        "Phone <-- tap/swipe/type --+\n"
        "         --> verify_postcondition (hash, OCR, orange/green)\n"
        "         --> RL / learned-screen / lessons update\n"
        "         --> next step or stagnation halt",
        s["code"],
    ))

    story.append(Paragraph("23. Document control", s["h1"]))
    story.append(Paragraph(
        "This brief describes engine <b>v24.0.115</b> as pushed to "
        "github.com/suvmitra/lion-opal-rose-moss (commit on branch main, "
        f"generated {generated}). It is not a specification of a future system. "
        "Where the code and this text disagree, the code in "
        "survey_engine/parts/ wins. Personal facts in knowledge_base.json "
        "(name, employer, child) are the operator's declared survey persona "
        "and should be treated as confidential.",
        s["body"],
    ))
    story.append(Paragraph(
        "Prepared for independent architectural review. Next refinement should "
        "be driven by the consultant's answers in §19, not by another "
        "one-screen coordinate patch unless that patch is the recommended path.",
        s["body"],
    ))

    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=18 * mm,
        bottomMargin=16 * mm,
        title="Survey Agent Architecture Brief v24.0.115",
        author="survey-agent / lion-opal-rose-moss",
        subject="Technical architecture for external expert review",
    )
    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    print("WROTE", OUT, "bytes", OUT.stat().st_size)


if __name__ == "__main__":
    build()
