# ==============================================================================
# File: human_answer_matching.py
# Project: Vision-Led Agentic Mobile Survey Automation
# Version: 24.0.17
#
# Stdlib-only helpers for operator key-in of unknown personal survey answers.
# Imported by survey_with_salad.py and unit-tested without ADB or Salad.
# If this sibling is missing, survey_with_salad.py v24.0.18 vendors the
# same functions so a single-file copy keeps working.
# ==============================================================================

from __future__ import annotations

import re
from typing import Any, Optional


OPTION_CHROME_LABELS = {
    "search",
    "privacy policy",
    "survey",
    "next",
    "continue",
    "back",
    "skip",
    "close",
    "reload",
    "cashout",
    "balance",
    "featured surveys",
    "more options",
    "accept",
    "reject",
}

QUESTION_KB_KEY_HINTS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("which of these pets",), "household_pets"),
    (("pets currently live",), "household_pets"),
    (("pets", "household"), "household_pets"),
    (("pets", "live with you"), "household_pets"),
)

NONE_TOKENS = {
    "none",
    "no",
    "no pets",
    "no pet",
    "n/a",
    "na",
    "nothing",
    "i do not have any pets",
    "i don't have any pets",
    "do not have any pets",
    "don't have any pets",
}

SKIP_TOKENS = {"skip", "quit", "abort", "exit", "cancel", "stop"}

_STOP_WORDS = {
    "which", "of", "these", "the", "a", "an", "to", "in", "your", "you",
    "with", "currently", "do", "does", "what", "is", "are", "for", "and",
    "or", "on", "at", "this", "that", "live",
}


def _normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("’", "'")).strip()


def option_match_keys(label: str) -> set[str]:
    """Expand a visible option into comparable tokens (Cat(s) -> cat, cats)."""
    text = _normalize_space(label).lower()
    if not text:
        return set()
    keys = {text, re.sub(r"[^a-z0-9]+", "", text)}
    stripped = _normalize_space(re.sub(r"\(s\)", "", text, flags=re.I))
    if stripped:
        keys.add(stripped)
        if not stripped.endswith("s"):
            keys.add(stripped + "s")
        else:
            keys.add(stripped[:-1])
    for inner in re.findall(r"\(([^)]+)\)", text):
        for part in re.split(r"[,/]| etc\.?", inner):
            part = _normalize_space(part).strip(" .")
            if part and part not in {"s", "etc"}:
                keys.add(part)
    stem = re.sub(r"[^a-z0-9 ]+", " ", stripped or text)
    stem = _normalize_space(stem)
    if stem:
        keys.add(stem)
        keys.update(stem.split())
    none_like = (
        "do not have" in text
        or "don't have" in text
        or "no pets" in text
        or text in NONE_TOKENS
    )
    if none_like:
        keys.update(NONE_TOKENS)
    return {key for key in keys if key}


def question_text_from_ocr(ocr_text: str) -> str:
    """Reconstruct the visible question, including wrapped lines before '?'."""
    pieces: list[str] = []
    for raw in str(ocr_text or "").splitlines():
        line = _normalize_space(raw)
        if not line:
            continue
        lowered = line.lower()
        if lowered in OPTION_CHROME_LABELS:
            if pieces:
                break
            continue
        pieces.append(line)
        if "?" in line:
            break
        if len(pieces) >= 6:
            break
    question = _normalize_space(" ".join(pieces))
    if "?" in question:
        question = question[: question.rfind("?") + 1]
    return question


def visible_answer_option_labels(
    ocr_text: str,
    node_labels: Optional[list[str]] = None,
) -> list[str]:
    """Collect unique visible answer labels, skipping chrome and the question."""
    labels: list[str] = []
    seen: set[str] = set()
    question = question_text_from_ocr(ocr_text).lower()

    def add(raw: str) -> None:
        label = _normalize_space(raw)
        if not label or len(label) < 2:
            return
        key = label.lower()
        if key in OPTION_CHROME_LABELS or key in seen:
            return
        if key.endswith("%") or re.fullmatch(r"\d{1,2}:\d{2}", key):
            return
        if "?" in label:
            return
        if question and (key in question or question in key):
            return
        seen.add(key)
        labels.append(label)

    for node_label in node_labels or []:
        add(node_label)

    past_question = False
    for raw in str(ocr_text or "").splitlines():
        line = _normalize_space(raw)
        if not line:
            continue
        lowered = line.lower()
        if not past_question:
            if "?" in line or lowered in OPTION_CHROME_LABELS:
                past_question = True
            continue
        if lowered in OPTION_CHROME_LABELS:
            continue
        add(line)

    return labels


def derive_question_kb_key(
    question: str,
    extra_hints: Optional[dict[str, tuple[str, ...]]] = None,
) -> str:
    """Map a visible question onto a stable knowledge-base key."""
    normalized = _normalize_space(question).lower()
    for hints, key in QUESTION_KB_KEY_HINTS:
        if all(hint in normalized for hint in hints):
            return key
    for key, hints in (extra_hints or {}).items():
        if any(hint in normalized for hint in hints):
            return key
    words = re.findall(r"[a-z0-9]+", normalized)
    kept = [word for word in words if word not in _STOP_WORDS][:6]
    slug = "_".join(kept) or "survey_answer"
    return re.sub(r"[^a-z0-9_]+", "_", slug).strip("_")


def intended_options_from_kb_value(value: Any) -> list[str]:
    """Normalize a stored KB answer into visible option labels."""
    if value in (None, ""):
        return []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if re.search(r"[,;]", text):
        return [part.strip() for part in re.split(r"[,;]", text) if part.strip()]
    return [text]


def _match_token_to_options(token: str, options: list[str]) -> Optional[str]:
    needle = _normalize_space(token).lower()
    if not needle:
        return None
    numbered = re.match(r"^(?:option|opt|choice|#)\s*(\d+)$", needle)
    if numbered:
        needle = numbered.group(1)
    if needle.isdigit():
        index = int(needle) - 1
        if 0 <= index < len(options):
            return options[index]
        return None
    needle_keys = option_match_keys(needle)
    exact: list[str] = []
    partial: list[str] = []
    for option in options:
        option_keys = option_match_keys(option)
        if needle in option_keys or option.lower() == needle:
            exact.append(option)
            continue
        if needle_keys & option_keys:
            exact.append(option)
            continue
        option_blob = " ".join(sorted(option_keys))
        if needle in option.lower() or option.lower() in needle:
            partial.append(option)
        elif any(key in option_blob for key in needle_keys if len(key) >= 3):
            partial.append(option)
    if exact:
        return exact[0]
    if len(partial) == 1:
        return partial[0]
    return None


def parse_human_answer_input(
    raw: str,
    options: list[str],
) -> tuple[str, list[str]]:
    """Parse operator text into grounded option labels.

    Returns (status, labels) where status is:
      ok | skip | empty | unmatched
    """
    text = _normalize_space(raw)
    if not text:
        return "empty", []
    lowered = text.lower()
    if lowered in SKIP_TOKENS:
        return "skip", []

    only_match = re.match(r"^only\s+(.+)$", text, flags=re.I)
    if only_match:
        text = _normalize_space(only_match.group(1))
        lowered = text.lower()

    if lowered in NONE_TOKENS:
        none_option = next(
            (option for option in options if NONE_TOKENS & option_match_keys(option)),
            None,
        )
        if none_option:
            return "ok", [none_option]
        return "unmatched", []

    tokens = [part for part in re.split(r"\s*(?:,|;|&|\band\b)\s*", text) if part]
    if not tokens:
        tokens = [text]

    matched: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        option = _match_token_to_options(token, options)
        if not option:
            continue
        key = option.lower()
        if key in seen:
            continue
        seen.add(key)
        matched.append(option)

    if matched:
        return "ok", matched
    return "unmatched", []


def fallback_keywords_from_question(question: str) -> list[str]:
    normalized = _normalize_space(question).lower()
    if "pets" in normalized and "household" in normalized:
        return ["pets currently live", "household"]
    words = [word for word in re.findall(r"[a-z0-9]+", normalized) if word not in _STOP_WORDS]
    phrases: list[str] = []
    if len(words) >= 2:
        phrases.append(" ".join(words[:3]))
    if words:
        phrases.append(words[0])
    return phrases[:3]
