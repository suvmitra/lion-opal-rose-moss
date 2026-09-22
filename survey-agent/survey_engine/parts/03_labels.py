# 03_labels.py — shared engine namespace (do not import directly)



def node_center(node: dict[str, Any]) -> tuple[int, int]:
    b = node["bounds"]
    return ((b[0] + b[2]) // 2, (b[1] + b[3]) // 2)


def node_text(node: dict[str, Any]) -> str:
    return " ".join(
        part for part in (
            str(node.get("text") or "").strip(),
            str(node.get("content_desc") or "").strip(),
        ) if part
    ).strip()


TERMINAL_SURVEY_PHRASES = (
    "survey is now closed",
    "survey is closed",
    "survey has closed",
    "survey is no longer available",
    "survey no longer available",
    "survey is unavailable",
    "quota is full",
    "quota full",
    "do not qualify",
    "didn't qualify",
    "did not qualify",
    "didn’t qualify",
    "not eligible for this survey",
    "not a match for this survey",
)


COOKIE_OVERLAY_PHRASES = (
    "your cookie choices",
    "cookie preferences",
    "cookie settings",
    "manage cookies",
    "powered by transcend",
    "we use cookies",
    "use cookies and similar technologies",
)


def normalized_lines(text: str) -> list[str]:
    """Return non-empty normalized lines without destroying CTA boundaries."""
    return [
        re.sub(r"\s+", " ", line).strip().lower()
        for line in str(text or "").splitlines()
        if re.sub(r"\s+", " ", line).strip()
    ]


def exact_label_node(
    nodes: list[dict[str, Any]], labels: tuple[str, ...] | list[str]
) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    """Find an exact UI label, avoiding prose that merely contains a CTA word."""
    wanted = {re.sub(r"\s+", " ", label.strip().lower()): label for label in labels}
    for node in nodes:
        text = re.sub(r"\s+", " ", node_text(node).strip().lower())
        if text in wanted:
            return node, wanted[text]
    return None, None


def visible_exact_label(
    ocr_text: str, labels: tuple[str, ...] | list[str]
) -> Optional[str]:
    """Return a CTA only when OCR exposes it as its own line."""
    wanted = {re.sub(r"\s+", " ", label.strip().lower()): label for label in labels}
    for line in normalized_lines(ocr_text):
        if line in wanted:
            return wanted[line]
        stripped = re.sub(r"[\s«»<>]+", " ", line).strip()
        if stripped in wanted:
            return wanted[stripped]
    return None


PROGRESSION_CTA_CORES = {"continue", "next", "proceed", "submit", "forward"}
BACK_CTA_CORES = {"back", "previous"}
FORBIDDEN_PROGRESSION_MARKERS = (
    "privacy", "accessibility", "help", "reload", "cashout", "balance",
    "open privacy", "close button",
)


def cta_core(text: str) -> str:
    """Strip chevrons/punctuation so 'Continue »' and '« Back' compare cleanly."""
    value = re.sub(r"[\s«»<>]+", " ", str(text or "").replace("’", "'").lower()).strip()
    return re.sub(r"\s+", " ", value)


def is_banner_or_instruction_label(text: str) -> bool:
    label = re.sub(r"\s+", " ", str(text or "")).strip()
    lowered = label.lower()
    return any(marker in lowered for marker in (
        "problems with some of the data",
        "questions with errors",
        "please select an answer",
        "please follow the instructions",
        "instructions attached",
        "please select one of the below",
        "there were problems",
        "this question is required",
        "question is required",
        "the chief income earner is the person",
        "consider yourself the",
        "if your income is equal",
        "largest income",
    ))


def is_chrome_option_label(text: str) -> bool:
    key = cta_core(text)
    if not key:
        return True
    if key in OPTION_CHROME_LABELS:
        return True
    return any(marker in key for marker in (
        "close button", "close this survey", "close survey", "go back",
        "privacy", "accessibility", "reload", "cashout", "help",
    )) or key in {"x", "×", "✕"}


def is_forbidden_progression_target(text: str) -> bool:
    core = cta_core(text)
    if not core:
        return True
    if core in BACK_CTA_CORES:
        return True
    return any(marker in core for marker in FORBIDDEN_PROGRESSION_MARKERS)


def is_progression_cta(text: str) -> bool:
    if is_forbidden_progression_target(text):
        return False
    core = cta_core(text)
    if core in PROGRESSION_CTA_CORES:
        return True
    first = core.split(" ", 1)[0] if core else ""
    return first in PROGRESSION_CTA_CORES


def visible_progression_label(ocr_text: str) -> Optional[str]:
    """Return the visible Continue/Next label, including chevron variants."""
    for raw in str(ocr_text or "").splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if is_progression_cta(line):
            return line
    match = re.search(
        r"\b(Continue\s*»?|Next\s*»?|Submit|Proceed)\b",
        str(ocr_text or ""),
        flags=re.I,
    )
    if match:
        return match.group(1)
    return None


def cookie_consent_visible(ocr_text: str, nodes: list[dict[str, Any]]) -> bool:
    """Require both cookie-overlay language and an explicit consent action."""
    visible = re.sub(r"\s+", " ", str(ocr_text or "").lower())
    structured = re.sub(
        r"\s+", " ", " ".join(node_text(node) for node in nodes if node_text(node)).lower()
    )
    combined = f"{visible} {structured}"
    strong_overlay_language = any(
        phrase in combined for phrase in ("your cookie choices", "powered by transcend")
    )
    overlay_language = any(phrase in combined for phrase in COOKIE_OVERLAY_PHRASES)
    consent_actions = sum(
        1 for label in ("accept", "reject", "more options", "allow all", "accept all")
        if re.search(rf"\b{re.escape(label)}\b", combined)
    )
    return strong_overlay_language or (overlay_language and consent_actions >= 1)


LANDING_CTA_LABELS = (
    "Participate", "Start!", "Start", "Start survey", "Begin survey", "Get started",
    "Accept and get started", "I have read and accept",
)


_START_SESSION: dict[str, int] = {"misses": 0}


def start_gate_visible(ocr_text: str) -> bool:
    blob = re.sub(r"\s+", " ", str(ocr_text or "").lower())
    if "start!" in blob:
        return True
    if "click on" in blob and "start" in blob:
        return True
    if "exciting survey opportunities" in blob and "start" in blob:
        return True
    return False


def start_ocr_button_milli(obs: Observation) -> Optional[list[int]]:
    """Only a short Start!/Start line. Never the word start inside a sentence."""
    path = str(obs.screenshot or "")
    if not path or not Path(path).exists():
        return None
    for psm in (6, 11):
        for node in ocr_line_nodes(Path(path), psm=psm):
            text = re.sub(r"\s+", " ", str(node_text(node) or "")).strip().lower()
            text = re.sub(r"[«»]", "", text).strip(" .")
            if text not in {"start!", "start", "start !"}:
                continue
            bounds = node.get("bounds") or []
            if len(bounds) != 4:
                continue
            cx = (int(bounds[0]) + int(bounds[2])) / 2
            cy = (int(bounds[1]) + int(bounds[3])) / 2
            y = int(cy * 1000 / max(1, obs.image_height))
            x = int(cx * 1000 / max(1, obs.image_width))
            if 360 <= y <= 480 and 250 <= x <= 750:
                return [x, y]
    return None


def visible_continue_milli(obs: Observation) -> Optional[list[int]]:
    """Screenshot OCR of footer Continue. Never accessibility dump y=92%."""
    path = str(obs.screenshot or "")
    if not path or not Path(path).exists():
        return None
    hits: list[list[int]] = []

    def consider(node: dict[str, Any]) -> None:
        text = re.sub(r"[\s«»]+", " ", str(node_text(node) or "")).strip().lower().strip(" .")
        if text not in {"continue", "continue »"} and not ("continue" in text and len(text) <= 14):
            return
        bounds = node.get("bounds") or []
        if len(bounds) != 4:
            return
        cx = (int(bounds[0]) + int(bounds[2])) / 2
        cy = (int(bounds[1]) + int(bounds[3])) / 2
        y = int(cy * 1000 / max(1, obs.image_height))
        x = int(cx * 1000 / max(1, obs.image_width))
        if 380 <= y <= 915 and 150 <= x <= 850:
            hits.append([x, y])

    for psm in (6, 11):
        for node in ocr_line_nodes(Path(path), psm=psm):
            consider(node)
    if not hits:
        try:
            with Image.open(path) as image:
                w, h = image.size
                y0 = int(h * 0.82)
                crop = image.convert("RGB").crop((0, y0, w, int(h * 0.94))).point(lambda p: 255 - p)
                data = pytesseract.image_to_data(
                    crop, output_type=pytesseract.Output.DICT, config="--oem 3 --psm 6"
                )
            for i, raw in enumerate(data.get("text") or []):
                if "continue" not in str(raw or "").strip().lower():
                    continue
                cx = int(data["left"][i]) + int(data["width"][i]) // 2
                cy = y0 + int(data["top"][i]) + int(data["height"][i]) // 2
                y = int(cy * 1000 / max(1, obs.image_height))
                x = int(cx * 1000 / max(1, obs.image_width))
                if 380 <= y <= 915:
                    hits.append([x, y])
        except Exception:
            pass
    if not hits:
        return None
    hits.sort(key=lambda p: p[1])
    pick = hits[-1]
    logger.info("[CONTINUE OCR] milli=%s hits=%s", pick, hits)
    return pick


def start_button_milli(obs: Observation) -> list[int]:
    """Green Start! pill center. Screenshot geometry: ~[500, 405] on 1440x3088."""
    variants: list[list[int]] = []
    try:
        pill = green_continue_pill_coords(obs, y0=0.36, y1=0.46)
        if pill and 360 <= int(pill[1]) <= 480:
            variants.append([int(pill[0]), int(pill[1])])
    except TypeError:
        pass
    ocr = start_ocr_button_milli(obs)
    if ocr:
        variants.append(ocr)
    for fallback in ([500, 405], [500, 420], [498, 390]):
        if fallback not in variants:
            variants.append(fallback)
    miss = int(_START_SESSION.get("misses") or 0)
    pick = variants[min(max(0, miss), len(variants) - 1)]
    logger.info("[START GATE] milli=%s miss=%s variants=%s", pick, miss, variants)
    return pick


def landing_cta_visible(ocr_text: str, nodes: list[dict[str, Any]]) -> bool:
    """Recognize actual landing CTAs, not the same words embedded in questions."""
    node, _ = exact_label_node(nodes, LANDING_CTA_LABELS)
    return bool(node or visible_exact_label(ocr_text, LANDING_CTA_LABELS))


def qualified_landing_visible(ocr_text: str) -> bool:
    """Detect a survey-ready landing page from currently rendered OCR only.

    UIAutomator may keep the survey catalog mounted behind this overlay, so no
    accessibility-node evidence is accepted here. Two independent landing cues
    are required unless the explicit qualified phrase and a standalone CTA are
    both visible.
    """
    visible = re.sub(
        r"\s+", " ", str(ocr_text or "").lower().replace("’", "'")
    )
    qualified = any(phrase in visible for phrase in (
        "you've qualified for this survey",
        "you have qualified for this survey",
        "you are qualified for this survey",
        "you qualify for this survey",
        "you are eligible for this survey",
        "we would like to get your feedback",
        "we would like your feedback",
    ))
    cues = sum(1 for phrase in (
        "click below to get started",
        "get started and earn",
        "survey will take around",
        "survey success tip",
    ) if phrase in visible)
    visible_cta = visible_exact_label(ocr_text, LANDING_CTA_LABELS)
    return bool(qualified or (qualified and visible_cta) or (qualified and cues >= 1) or cues >= 2)


def text_entry_question_visible(ocr_text: str, nodes: list[dict[str, Any]]) -> bool:
    """Recognize form questions whose WebView hides the editable input node."""
    combined = re.sub(
        r"\s+", " ",
        " ".join([str(ocr_text or "")] + [node_text(node) for node in nodes if node_text(node)]).lower(),
    )
    if any(node.get("editable") and node.get("enabled") for node in nodes):
        return True
    strong_terms = (
        "postcode", "postal code", "zip code", "eircode",
        "email address", "phone number", "telephone number",
        "what is your age", "your age", "how old are you",
        "full name", "your name", "enter a number",
        "whole number", "state their ages", "their ages",
    )
    entry_cues = (
        "e.g.", "e.g,", "eg.", "example", "a96", " for ie",
        "enter", "type", "provide", "your ", "number",
    )
    if any(term in combined for term in (
        "enter a number", "enter a whole number", "what is your age",
        "state their ages", "whole number",
    )):
        return True
    return any(term in combined for term in strong_terms) and any(
        cue in combined for cue in entry_cues
    )


def permission_dialog_visible(ocr_text: str, nodes: list[dict[str, Any]]) -> bool:
    combined = re.sub(
        r"\s+", " ",
        " ".join([str(ocr_text or "")] + [node_text(node) for node in nodes if node_text(node)]).lower(),
    )
    permission_language = any(term in combined for term in (
        "allow this app", "while using the app", "only this time",
        "don't allow", "allow access to", "permission",
    ))
    action_language = any(term in combined for term in (
        "allow", "don't allow", "deny", "only this time",
    ))
    return permission_language and action_language


def document_picker_visible(ocr_text: str, nodes: list[dict[str, Any]]) -> bool:
    packages = " ".join(str(node.get("package") or "") for node in nodes).lower()
    if "documentsui" in packages:
        return True
    visible = re.sub(r"\s+", " ", str(ocr_text or "").lower())
    return (
        any(term in visible for term in ("open from", "recent files", "downloads", "use this folder"))
        and any(term in visible for term in ("open", "cancel", "files", "documents"))
    )


def dashboard_evidence(ocr_text: str, nodes: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    """Recognize the app home screen even when one OCR header is missed.

    The production failure behind v24.0.14 contained multiple unmistakable home
    markers (Balance, Cashout, game tabs, reward cards and bottom navigation),
    but the old classifier depended too heavily on the exact Featured Surveys
    phrase.  Requiring combinations of independent markers is both more robust
    and safer than treating an arbitrary question mark or hidden WebView node as
    a survey question.
    """
    visible = re.sub(r"\s+", " ", str(ocr_text or "").lower().replace("’", "'"))
    structured = re.sub(
        r"\s+", " ", " ".join(node_text(node) for node in nodes if node_text(node)).lower()
    )
    combined = f"{visible} {structured}"
    reasons: list[str] = []

    account_header = "balance" in visible and "cashout" in visible
    featured_visible = "featured surveys" in visible or "featured survey" in visible
    featured_structured = "featured surveys" in structured or "featured survey" in structured
    game_tabs_visible = (
        ("best games" in visible and "my games" in visible)
        or ("best garnes" in visible and "my garnes" in visible)
    )
    game_tabs_structured = (
        ("best games" in structured and "my games" in structured)
        or ("best garnes" in structured and "my garnes" in structured)
    )
    # Stale accessibility nodes can remain exposed behind a Qualification or
    # terminal WebView. Structured-only markers therefore need the visibly
    # rendered Balance/Cashout header before they can prove dashboard state.
    featured = featured_visible or (featured_structured and account_header)
    game_tabs = game_tabs_visible or (game_tabs_structured and account_header)
    empty_games = any(term in combined for term in (
        "haven't started any games", "have not started any games", "explore games",
    ))
    survey_catalog_tabs_visible = (
        ("best match" in visible and "short surveys" in visible)
        or ("short surveys" in visible and "highest payout" in visible)
        or ("best match" in visible and "highest payout" in visible)
    )
    survey_catalog_tabs_structured = (
        ("best match" in structured and "short surveys" in structured)
        or ("short surveys" in structured and "highest payout" in structured)
        or ("best match" in structured and "highest payout" in structured)
    )
    nav_hits = sum(
        1 for label in ("earn", "surveys", "games", "account")
        if re.search(rf"\b{label}\b", combined)
    )
    payout_count = len(re.findall(r"[€$£]\s*\d+(?:[.,]\d+)?", combined))
    duration_count = len(re.findall(r"\b\d{1,3}\s*min\b", combined))

    if featured:
        reasons.append("featured-surveys")
    if game_tabs:
        reasons.append("game-tabs")
    if account_header:
        reasons.append("balance-cashout")
    if empty_games:
        reasons.append("empty-games-panel")
    if survey_catalog_tabs_visible:
        reasons.append("survey-catalog-tabs")
    elif survey_catalog_tabs_structured and account_header:
        reasons.append("structured-survey-catalog-tabs")
    if nav_hits >= 3:
        reasons.append("bottom-navigation")
    if payout_count >= 3 and duration_count >= 2:
        reasons.append("reward-card-grid")

    # One explicit dashboard section is sufficient.  Otherwise require the
    # account header plus another independent home-screen feature.
    visible_dashboard = bool(
        featured
        or game_tabs
        or survey_catalog_tabs_visible
        or (survey_catalog_tabs_structured and account_header)
        or (account_header and (empty_games or nav_hits >= 3 or (payout_count >= 3 and duration_count >= 2)))
        or (empty_games and nav_hits >= 3 and payout_count >= 2)
        or (nav_hits >= 3 and payout_count >= 4 and duration_count >= 3)
    )
    return visible_dashboard, reasons


def dashboard_chrome_target(target_text: str) -> bool:
    """Return True for labels that must never be treated as survey answers."""
    normalized = re.sub(r"\s+", " ", str(target_text or "").strip().lower())
    if not normalized:
        return False
    if normalized in {
        "balance", "balance:", "cashout", "earn", "surveys", "games", "account",
        "best games", "my games", "featured surveys",
    }:
        return True
    return bool(re.fullmatch(r"[€$£]\s*\d+(?:[.,]\d+)?(?:\s*/\s*[€$£]\s*\d+(?:[.,]\d+)?)?", normalized))


