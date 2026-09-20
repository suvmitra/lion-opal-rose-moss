# 06_learning.py — shared engine namespace (do not import directly)



def update_kb(
    key: str,
    value: Any,
    reason: str = "LLM-derived survey mapping",
    provenance: str = "declared",
    confidence: float = 1.0,
    question: str = "",
    source_basis: str = "",
) -> None:
    ck = canonical_key(key)
    if not ck or value in (None, ""):
        return
    kb = load_kb()
    old = kb.get(ck)
    kb[ck] = value

    metadata = kb.get("answer_metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    metadata[ck] = {
        "provenance": provenance if provenance in {"verified", "declared", "inferred"} else "inferred",
        "confidence": round(max(0.0, min(1.0, float(confidence))), 2),
        "question": str(question)[:300],
        "source_basis": str(source_basis)[:500],
        "updated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    kb["answer_metadata"] = metadata
    save_kb(kb)
    logger.info(
        "[KB] %s: %r -> %r | provenance=%s confidence=%.2f | %s",
        ck, old, value, provenance, confidence, reason
    )


def semantic_screen_signature(obs: Observation) -> str:
    """Create a stable, non-image screen key while ignoring clock/battery noise."""
    text = str(obs.ocr_text or "").lower().replace("’", "'")
    text = re.sub(r"\b\d{1,2}:\d{2}\b", "<time>", text)
    text = re.sub(r"\b\d{1,3}%\b", "<percent>", text)
    text = re.sub(r"\s+", " ", text).strip()
    node_labels = sorted({
        re.sub(r"\s+", " ", node_text(node).lower()).strip()
        for node in obs.ui_nodes
        if node_text(node).strip()
    })
    material = json.dumps(
        {
            "phase": obs.screen_phase,
            "ocr": text[:1800],
            "labels": node_labels[:80],
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]


def learned_confidence(successes: int, failures: int) -> float:
    """Smoothed confidence: one verified success reaches 0.80; failures demote fast."""
    return round((max(0, successes) + 3) / (max(0, successes) + max(0, failures) + 4), 3)


DEFAULT_SURVEY_LESSONS: dict[str, dict[str, Any]] = {
    "child_ages_text": {
        "stems": ["state their ages", "enter a whole number", "specify a whole number"],
        "kb_key": "child_age",
        "router": "child_age_text_decision",
    },
    "dependent_children_count": {
        "stems": ["how many dependent children", "children (under 18)"],
        "kb_key": "number_of_children",
        "router": "dependent_children_decision",
    },
    "bread_carousel": {
        "stems": ["select one in each row", "types of bread bought"],
        "router": "carousel_row_decision",
    },
}


def _lesson_stems_from_ocr(ocr_text: str) -> list[str]:
    text = re.sub(r"\s+", " ", str(ocr_text or "").lower())
    text = re.sub(r"\b\d{1,2}:\d{2}\b", "", text)
    text = re.sub(r"\b\d{1,3}%\b", "", text)
    stems: list[str] = []
    for lesson in DEFAULT_SURVEY_LESSONS.values():
        for stem in lesson.get("stems") or []:
            if stem in text and stem not in stems:
                stems.append(stem)
    q = current_question_text(
        Observation(
            step=0, screenshot=None, image_width=1, image_height=1,
            device_width=1, device_height=1, screen_hash="", ocr_text=ocr_text,
            ui_nodes=[], kb={}, persona={}, screen_phase="survey_question", survey_tiles=[],
        )
    ) if False else ""
    # Keep a short visible question stem even when it is a new pattern.
    blob = re.sub(r"[^a-z0-9 ]+", " ", text)
    words = [w for w in blob.split() if len(w) > 3][:8]
    if words:
        stems.append(" ".join(words[:6]))
    return stems[:6]


def improve_survey_intelligence(
    obs: Observation,
    decision: Optional[dict[str, Any]],
    *,
    verified: bool,
    source: str = "router",
    issue: str = "",
) -> None:
    """Continuously store what worked (or failed) for a question stem.

    Next similar screens are solved by lesson_action_decision before the VLM.
    """
    if not decision:
        return
    action = str(decision.get("action") or "").lower()
    if action in {"wait", "finish"}:
        return
    stems = _lesson_stems_from_ocr(obs.ocr_text)
    if not stems:
        return
    lid = hashlib.sha256("|".join(stems).encode("utf-8")).hexdigest()[:12]
    try:
        kb = load_kb()
    except Exception:
        return
    lessons = kb.get("survey_lessons")
    if not isinstance(lessons, dict):
        lessons = dict(DEFAULT_SURVEY_LESSONS)
    entry = lessons.get(lid) if isinstance(lessons.get(lid), dict) else {
        "stems": stems,
        "successes": 0,
        "failures": 0,
        "kb_key": decision.get("kb_key"),
        "decision": {},
    }
    if verified:
        template = {
            key: decision.get(key)
            for key in ("action", "target_text", "kb_key", "input_payload", "postcondition")
            if decision.get(key) not in (None, "")
        }
        entry["successes"] = int(entry.get("successes") or 0) + 1
        entry["decision"] = template
        entry["kb_key"] = decision.get("kb_key") or entry.get("kb_key")
        entry["last_issue"] = ""
    else:
        entry["failures"] = int(entry.get("failures") or 0) + 1
        entry["last_issue"] = str(issue or action)[:200]
    entry["stems"] = stems
    entry["updated_at_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lessons[lid] = entry
    for key, seeded in DEFAULT_SURVEY_LESSONS.items():
        lessons.setdefault(key, dict(seeded))
    kb["survey_lessons"] = lessons
    try:
        save_kb(kb)
        logger.info(
            "[LESSON] %s verified=%s action=%s key=%s successes=%s failures=%s",
            lid, verified, action, entry.get("kb_key"),
            entry.get("successes"), entry.get("failures"),
        )
    except Exception as exc:
        logger.debug("[LESSON] persist skipped: %s", exc)


def lesson_action_decision(obs: Observation) -> Optional[dict[str, Any]]:
    """Replay a stored lesson or a seeded router for the visible question."""
    blob = re.sub(r"\s+", " ", str(obs.ocr_text or "").lower())
    lessons: dict[str, Any] = dict(DEFAULT_SURVEY_LESSONS)
    stored = (obs.kb or {}).get("survey_lessons")
    if isinstance(stored, dict):
        lessons.update(stored)
    for lesson in lessons.values():
        if not isinstance(lesson, dict):
            continue
        stems = [str(s).lower() for s in (lesson.get("stems") or []) if s]
        if not stems or not any(stem in blob for stem in stems):
            continue
        router = str(lesson.get("router") or "")
        if router == "child_age_text_decision":
            return child_age_text_decision(obs)
        if router == "dependent_children_decision":
            return dependent_children_decision(obs)
        if router == "carousel_row_decision":
            return carousel_row_decision(obs)
        kb_key = str(lesson.get("kb_key") or "")
        template = lesson.get("decision") if isinstance(lesson.get("decision"), dict) else {}
        action = str(template.get("action") or "")
        if action == "type_text" and kb_key:
            value = kb_or_persona_value(obs, kb_key)
            if value in (None, ""):
                return capture_human_answer_decision(
                    obs, f"{kb_key} is not in knowledge_base.json."
                )
            decision = dict(template)
            decision["input_payload"] = str(value).strip()
            decision["kb_key"] = kb_key
            decision["confidence_score"] = 0.93
            logger.info("[LESSON] Replaying type_text kb_key=%s", kb_key)
            return decision
    return None


def learned_action_decision(obs: Observation) -> Optional[dict[str, Any]]:
    """Reuse a verified semantic-screen action only while its confidence is high."""
    if obs.screen_phase != "survey_question":
        return None
    if gender_choice_screen(obs):
        return None
    learned = obs.kb.get("learned_screen_actions")
    if not isinstance(learned, dict):
        return None
    signature = semantic_screen_signature(obs)
    entry = learned.get(signature)
    if not isinstance(entry, dict):
        widget = generalized_widget_class(obs)
        stem = question_stem_key(obs)
        for item in learned.values():
            if not isinstance(item, dict):
                continue
            if str(item.get("widget") or "") == widget and str(item.get("stem") or "") == stem and stem:
                entry = item
                signature = stem
                break
    if not isinstance(entry, dict):
        return None
    successes = int(entry.get("successes") or 0)
    failures = int(entry.get("failures") or 0)
    confidence = learned_confidence(successes, failures)
    if confidence < LEARNED_ACTION_MIN_CONFIDENCE:
        logger.info(
            "[LEARNED SCREEN] signature=%s confidence=%.3f below threshold=%.3f",
            signature, confidence, LEARNED_ACTION_MIN_CONFIDENCE,
        )
        return None
    template = entry.get("decision")
    if not isinstance(template, dict):
        return None
    decision = dict(template)
    kb_key = canonical_key(str(decision.get("kb_key") or ""))
    if str(decision.get("action") or "").lower() in {"type_text", "type_comment"} and kb_key:
        current_value = obs.kb.get(kb_key)
        if current_value in (None, ""):
            return None
        decision["input_payload"] = str(current_value)
    decision.update({
        "screen_state": obs.screen_phase,
        "confidence_score": confidence,
        "answer_reason": "Reusing a previously verified action for this semantic screen.",
        "source_basis": (
            f"Verified learned-screen action: successes={successes}, failures={failures}"
        ),
        "learned_signature": signature,
        "learned_action_confidence": confidence,
        "expected_next_signature": entry.get("next_signature"),
        "answer_provenance": str(decision.get("answer_provenance") or "verified"),
    })
    target = str(decision.get("target_text") or "").strip()
    action = str(decision.get("action") or "").lower()
    if action in {"click", "select_option", "toggle_checkbox"} and target and not is_progression_cta(target):
        keys = {target.lower()} | option_match_keys(target)
        last = (
            _LAST_SELECT_FINGERPRINT.get(question_fingerprint(obs), "")
            or _LAST_SELECT_FINGERPRINT.get(semantic_screen_signature(obs), "")
        )
        already = bool(keys & selected_option_labels(obs)) or answer_already_selected(obs)
        if already or (last and (last == target.lower() or last in keys)):
            logger.info("[LEARNED SCREEN] %r already selected; Continue instead of re-tap.", target)
            return None
    logger.info(
        "[LEARNED SCREEN] Reusing signature=%s action=%s target=%r confidence=%.3f",
        signature, decision.get("action"), decision.get("target_text"), confidence,
    )
    return decision


def update_learned_screen_action(
    obs: Observation,
    decision: dict[str, Any],
    verified: bool,
    decision_source: str,
    after: Optional[Observation] = None,
) -> None:
    """Persist verified LLM actions; update confidence for learned replays."""
    if obs.screen_phase not in {"survey_question", "navigation", "survey_landing"}:
        return
    if decision_source not in {
        "llm", "learned", "salad", "gemini-lite", "gemini-flash", "vlm",
        "router", "rl", "generalized",
    }:
        return
    if decision_source == "learned" and not verified:
        signature = str(decision.get("learned_signature") or semantic_screen_signature(obs))
        kb = load_kb()
        learned = kb.get("learned_screen_actions")
        if not isinstance(learned, dict):
            return
        existing = learned.get(signature)
        if not isinstance(existing, dict):
            return
        existing["failures"] = int(existing.get("failures") or 0) + 1
        existing["confidence"] = learned_confidence(
            int(existing.get("successes") or 0), int(existing.get("failures") or 0)
        )
        existing["updated_at_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        learned[signature] = existing
        kb["learned_screen_actions"] = learned
        save_kb(kb)
        logger.info(
            "[LEARNED SCREEN] Replay failed signature=%s failures=%s confidence=%s",
            signature, existing.get("failures"), existing.get("confidence"),
        )
        return
    action = str(decision.get("action") or "").lower()
    if action not in {
        "click", "select_option", "toggle_checkbox", "select_dropdown",
        "open_dropdown", "select_matrix_cell", "type_text", "type_comment",
        "scroll_down", "scroll_up", "scroll_left", "scroll_right", "swipe",
        "drag", "set_slider", "open_date_picker", "open_time_picker",
        "set_picker_value", "keyevent",
    }:
        return
    signature = str(decision.get("learned_signature") or semantic_screen_signature(obs))
    kb = load_kb()
    learned = kb.get("learned_screen_actions")
    if not isinstance(learned, dict):
        learned = {}
    existing = learned.get(signature)

    if not verified:
        if decision_source != "learned" or not isinstance(existing, dict):
            return
        existing["failures"] = int(existing.get("failures") or 0) + 1
        existing["confidence"] = learned_confidence(
            int(existing.get("successes") or 0), int(existing.get("failures") or 0)
        )
        existing["updated_at_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        learned[signature] = existing
    else:
        coords = decision.get("target_coords")
        safe_coords = coords if isinstance(coords, list) and len(coords) == 2 else None
        template = {
            key: decision.get(key)
            for key in (
                "action", "target_text", "input_payload", "kb_key", "kb_write",
                "postcondition", "answer_provenance", "keyevent", "gesture_start",
                "gesture_end", "control_value", "row_text", "column_text",
                "selection_complete",
            )
            if decision.get(key) not in (None, "")
        }
        if safe_coords:
            template["target_coords"] = safe_coords
        if action in {"type_text", "type_comment"} and not template.get("kb_key"):
            return
        same_template = bool(
            isinstance(existing, dict) and existing.get("decision") == template
        )
        successes = int(existing.get("successes") or 0) + 1 if same_template else 1
        failures = int(existing.get("failures") or 0) if same_template else 0
        learned[signature] = {
            "phase": obs.screen_phase,
            "widget": generalized_widget_class(obs),
            "stem": question_stem_key(obs),
            "decision": template,
            "successes": successes,
            "failures": failures,
            "confidence": learned_confidence(successes, failures),
            "next_signature": semantic_screen_signature(after) if after else None,
            "transition_successes": (
                int(existing.get("transition_successes") or 0) + 1
                if same_template and after else (1 if after else 0)
            ),
            "updated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }

    if len(learned) > MAX_LEARNED_SCREEN_ACTIONS:
        ordered = sorted(
            learned.items(), key=lambda item: str(item[1].get("updated_at_utc") or "")
        )
        learned = dict(ordered[-MAX_LEARNED_SCREEN_ACTIONS:])
    kb["learned_screen_actions"] = learned
    save_kb(kb)
    entry = learned.get(signature, {})
    logger.info(
        "[LEARNED SCREEN] Updated signature=%s verified=%s successes=%s failures=%s confidence=%s",
        signature, verified, entry.get("successes"), entry.get("failures"), entry.get("confidence"),
    )


RL_ALPHA = 0.35
RL_EPSILON = 0.12
RL_MIN_Q = 0.50
RL_POLICY_MAX = 80
_OPTION_CHROME = (
    "survey", "continue", "accessibility", "select one", "select all",
    "please select", "problems with", "there were", "instructions",
    "screen ", "english", "help",
)


def strip_transient_ocr(text: str) -> str:
    blob = re.sub(r"\s+", " ", str(text or "").lower())
    blob = blob.replace("’", "'")
    blob = re.sub(r"\b\d{1,2}:\d{2}\b", " ", blob)
    blob = re.sub(r"\b\d{1,3}%\b", " ", blob)
    blob = re.sub(r"there were problems with some of the data you entered in the survey[^.]{0,200}", " ", blob)
    blob = re.sub(r"you will find the questions with errors below.{0,80}", " ", blob)
    blob = re.sub(r"please follow the instructions attached to each question", " ", blob)
    blob = re.sub(r"you selected\s+\d+", " ", blob)
    blob = re.sub(r"screen\s+\d+\s+of\s+\d+", " ", blob)
    return re.sub(r"\s+", " ", blob).strip()


def generalized_widget_class(obs: Observation) -> str:
    return generalized_widget_class_from_text(obs.ocr_text, obs.screen_phase)


def generalized_widget_class_from_text(ocr_text: str, phase: str = "") -> str:
    blob = strip_transient_ocr(ocr_text)
    if phase == "dashboard":
        return "dashboard"
    if select_all_apply_visible(ocr_text):
        return "select_all"
    if looks_like_single_choice(ocr_text) or "please select an answer" in blob:
        return "select_one"
    if open_text_question_visible(ocr_text):
        return "open_text"
    if ranking_question_visible(ocr_text):
        return "rank"
    if "most important" in blob and "least important" in blob:
        return "maxdiff"
    if county_question_visible(ocr_text):
        return "dropdown"
    if "continue" in blob or "next" in blob:
        if "select" in blob or "?" in (ocr_text or ""):
            return "select_one" if "select one" in blob else "unknown"
        return "continue"
    return "unknown"


def question_stem_key(obs: Observation) -> str:
    blob = strip_transient_ocr(obs.ocr_text)
    words = [w for w in re.findall(r"[a-z]{3,}", blob) if w not in {
        "survey", "please", "select", "continue", "that", "this", "with", "from",
        "have", "your", "would", "when", "which",
    }]
    return " ".join(words[:8])


def policy_state_key(obs: Observation) -> str:
    return f"{generalized_widget_class(obs)}|{question_stem_key(obs)[:48]}"


def option_labels_from_ocr(obs: Observation) -> list[str]:
    labels: list[str] = []
    for raw in str(obs.ocr_text or "").splitlines():
        line = raw.strip()
        if len(line) < 2 or len(line) > 80:
            continue
        low = line.lower()
        if any(tok in low for tok in _OPTION_CHROME):
            continue
        if re.match(r"^[\d.:%]+$", line):
            continue
        if line not in labels:
            labels.append(line)
    return labels[:12]


def pick_option_assumption(labels: list[str]) -> Optional[str]:
    preferred = ("buy another", "yes", "agree", "employed", "brennan", "dublin", "male")
    skip = ("none of these", "prefer not", "don't know", "not sure", "skip", "other please")
    for lab in labels:
        if any(p in lab.lower() for p in preferred):
            return lab
    for lab in labels:
        if not any(s in lab.lower() for s in skip):
            return lab
    return labels[0] if labels else None


def _continue_decision(obs: Observation, reason: str, payload: Optional[str] = None) -> dict[str, Any]:
    found = None
    try:
        found = maxdiff_continue_coords(obs) or continue_button_on_screen(obs)
    except Exception:
        found = None
    coords = found[0] if found else [500, 780]
    label = found[1] if found and len(found) > 1 else "Continue »"
    return {
        "screen_state": "survey_question",
        "question_text": current_question_text(obs),
        "answer_reason": reason,
        "action": "click",
        "target_element_id": None,
        "target_text": label,
        "target_coords": coords,
        "coordinate_authoritative": True,
        "input_payload": payload,
        "confidence_score": 0.9,
        "postcondition": "screen changed",
        "generalized": True,
    }


def generalized_unseen_router(obs: Observation) -> Optional[dict[str, Any]]:
    """Assumption-based action for widget families the specialized routers missed."""
    if i_agree_consent_visible(obs.ocr_text):
        return i_agree_consent_decision(obs)
    if obs.screen_phase == "dashboard":
        return None
    if ranking_question_visible(obs.ocr_text) or maxdiff_question_visible(obs.ocr_text):
        return None
    if captcha_code_question_visible(obs.ocr_text) or drag_drop_question_visible(obs.ocr_text):
        return None
    widget = generalized_widget_class(obs)
    blob = strip_transient_ocr(obs.ocr_text)
    lime = 0
    try:
        lime = select_all_lime_band_count(obs)
    except Exception:
        lime = 0
    if lime >= 1 and widget in {"select_one", "select_all", "unknown"}:
        if start_gate_visible(obs.ocr_text) or qualified_landing_visible(obs.ocr_text):
            pass
        else:
            return _continue_decision(obs, "Green row is visible; Continue.", payload="selected")
    if widget == "select_one":
        fill = single_choice_radio_decision(obs)
        if fill:
            fill["generalized"] = True
            return fill
        pick = pick_option_assumption(option_labels_from_ocr(obs))
        if not pick:
            return None
        logger.info("[GENERALIZE] Unseen select-one assumed %r", pick)
        return {
            "screen_state": "survey_question",
            "question_text": current_question_text(obs),
            "answer_reason": f"Unseen Select-one; assumed {pick}.",
            "action": "select_option",
            "target_text": pick,
            "target_coords": [200, 500 if "problems with" in blob else 420],
            "coordinate_authoritative": True,
            "input_payload": pick,
            "confidence_score": 0.86,
            "postcondition": "selected option is " + pick,
            "generalized": True,
        }
    if widget == "select_all":
        return select_all_apply_decision(obs)
    if widget == "open_text":
        return open_text_answer_decision(obs)
    if widget == "continue":
        return _continue_decision(obs, "Continue is the only visible action.")
    labels = option_labels_from_ocr(obs)
    if labels and ("select" in blob or "which of" in blob or "would you" in blob):
        pick = pick_option_assumption(labels)
        if pick:
            logger.info("[GENERALIZE] Unknown screen treated as select-one pick=%r", pick)
            return {
                "screen_state": "survey_question",
                "question_text": current_question_text(obs),
                "answer_reason": f"Unknown question; assumed {pick}.",
                "action": "select_option",
                "target_text": pick,
                "target_coords": [200, 480],
                "coordinate_authoritative": True,
                "input_payload": pick,
                "confidence_score": 0.8,
                "postcondition": "selected option is " + pick,
                "generalized": True,
            }
    if "continue" in blob and "please select" not in blob:
        return _continue_decision(obs, "No empty radio; tap Continue.")
    return None


def _load_rl_policy() -> dict[str, Any]:
    try:
        kb = load_kb()
    except Exception:
        return {}
    policy = kb.get("rl_policy")
    return policy if isinstance(policy, dict) else {}


def _save_rl_policy(policy: dict[str, Any]) -> None:
    try:
        kb = load_kb()
        if len(policy) > RL_POLICY_MAX:
            ordered = sorted(policy.items(), key=lambda item: str((item[1] or {}).get("updated") or ""))
            policy = dict(ordered[-RL_POLICY_MAX:])
        kb["rl_policy"] = policy
        save_kb(kb)
    except Exception as exc:
        logger.debug("[RL] persist skipped: %s", exc)


def rl_action_id(decision: dict[str, Any]) -> str:
    action = str(decision.get("action") or "click")
    payload = str(decision.get("input_payload") or decision.get("target_text") or "")[:80]
    return f"{action}|{payload.lower().strip()}"


def rl_policy_decision(obs: Observation) -> Optional[dict[str, Any]]:
    """Replay the highest-Q action for this widget class / stem."""
    policy = _load_rl_policy()
    if not policy:
        return None
    state = policy_state_key(obs)
    widget = generalized_widget_class(obs)
    entry = policy.get(state) if isinstance(policy.get(state), dict) else None
    if not entry:
        class_key = f"{widget}|"
        best = None
        best_q = RL_MIN_Q
        for key, item in policy.items():
            if not str(key).startswith(class_key) or not isinstance(item, dict):
                continue
            q = float(item.get("q") or 0)
            if q > best_q:
                best_q = q
                best = item
        entry = best
    if not isinstance(entry, dict):
        return None
    q = float(entry.get("q") or 0)
    if q < RL_MIN_Q:
        return None
    template = entry.get("decision") if isinstance(entry.get("decision"), dict) else {}
    action = str(template.get("action") or "")
    if action in {"select_then_continue", "select_option"} and looks_like_single_choice(obs.ocr_text):
        fill = single_choice_radio_decision(obs)
        if fill:
            fill["rl_replay"] = True
            return fill
    if action not in {"select_option", "click", "type_text", "scroll_down"}:
        return None
    if action == "click" and is_progression_cta(str(template.get("target_text") or "Continue")):
        if start_gate_visible(obs.ocr_text):
            return None
        if "please select an answer" in strip_transient_ocr(obs.ocr_text):
            return None
        decision = _continue_decision(obs, f"RL replay Continue q={q:.2f}", payload=template.get("input_payload"))
        decision["rl_replay"] = True
        decision["confidence_score"] = min(0.94, 0.7 + q * 0.2)
        return decision
    if action == "select_option":
        pick = str(template.get("input_payload") or template.get("target_text") or "")
        if not pick:
            pick = pick_option_assumption(option_labels_from_ocr(obs)) or ""
        if not pick:
            return None
        logger.info("[RL] Replay select_option %r q=%.2f state=%s", pick, q, state)
        return {
            "screen_state": "survey_question",
            "question_text": current_question_text(obs),
            "answer_reason": f"RL policy replay q={q:.2f}: {pick}",
            "action": "select_option",
            "target_text": pick,
            "target_coords": template.get("target_coords") or [200, 480],
            "coordinate_authoritative": True,
            "input_payload": pick,
            "confidence_score": min(0.94, 0.7 + q * 0.2),
            "postcondition": "selected option is " + pick,
            "rl_replay": True,
        }
    if action == "type_text" and template.get("input_payload"):
        decision = dict(template)
        decision["rl_replay"] = True
        decision["confidence_score"] = min(0.94, 0.7 + q * 0.2)
        return decision
    if action == "scroll_down":
        return {
            "action": "scroll_down",
            "answer_reason": f"RL replay scroll q={q:.2f}",
            "confidence_score": 0.85,
            "postcondition": "screen changed",
            "rl_replay": True,
        }
    return None


def update_rl_policy(
    obs: Observation,
    decision: dict[str, Any],
    verified: bool,
    after: Optional[Observation] = None,
) -> None:
    """Bandit / Q update: verified progress is rewarded, empty Continue is punished."""
    if not decision:
        return
    action = str(decision.get("action") or "")
    if action in {"wait", "finish", "request_human"}:
        return
    reward = 1.0 if verified else -0.5
    if action in {"click"} and is_progression_cta(str(decision.get("target_text") or "")):
        if not decision.get("input_payload") and "please select an answer" in strip_transient_ocr(obs.ocr_text):
            reward = -1.0
        elif verified:
            reward = 1.2
    if not verified and after is not None:
        try:
            if select_all_lime_band_count(after) > select_all_lime_band_count(obs):
                reward = 0.7
        except Exception:
            pass
    state = policy_state_key(obs)
    aid = rl_action_id(decision)
    policy = _load_rl_policy()
    entry = policy.get(state) if isinstance(policy.get(state), dict) else {
        "q": 0.5, "n": 0, "action_id": aid, "decision": {},
    }
    old = float(entry.get("q") or 0.5)
    q = (1.0 - RL_ALPHA) * old + RL_ALPHA * reward
    template = {
        key: decision.get(key)
        for key in ("action", "target_text", "input_payload", "kb_key", "postcondition")
        if decision.get(key) not in (None, "")
    }
    coords = decision.get("target_coords")
    if isinstance(coords, list) and len(coords) == 2:
        template["target_coords"] = coords
    if verified or q >= float(entry.get("q") or 0):
        entry["decision"] = template
        entry["action_id"] = aid
    entry["q"] = round(q, 3)
    entry["n"] = int(entry.get("n") or 0) + 1
    entry["reward"] = reward
    entry["widget"] = generalized_widget_class(obs)
    entry["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    policy[state] = entry
    class_key = f"{entry['widget']}|*"
    class_entry = policy.get(class_key) if isinstance(policy.get(class_key), dict) else dict(entry)
    class_q = float(class_entry.get("q") or 0.5)
    class_entry["q"] = round((1.0 - RL_ALPHA * 0.5) * class_q + (RL_ALPHA * 0.5) * reward, 3)
    if verified:
        class_entry["decision"] = template
        class_entry["action_id"] = aid
    class_entry["n"] = int(class_entry.get("n") or 0) + 1
    class_entry["widget"] = entry["widget"]
    class_entry["updated"] = entry["updated"]
    policy[class_key] = class_entry
    _save_rl_policy(policy)
    logger.info("[RL] state=%s action=%s reward=%.2f q=%.3f n=%s", state, aid, reward, entry["q"], entry["n"])
