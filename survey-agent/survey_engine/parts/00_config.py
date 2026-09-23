# 00_config.py — shared engine namespace (do not import directly)

from __future__ import annotations

import base64
import ast
import csv
import io
import json
import logging
import os
import re
import subprocess
import sys
import time
import hashlib
import shutil
import importlib.util
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:
    import cv2
    import numpy as np
    from dotenv import load_dotenv
    from PIL import Image
    import imagehash
    import pytesseract
    import requests
except ImportError as exc:
    print(f"Missing Python dependency: {exc}")
    print("Install with: pip install -r requirements.txt")
    raise SystemExit(1)


VERSION = "24.0.138"
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True)

ADB_PATH = os.getenv("ADB_PATH", r"C:\adb\adb.exe")
TESSERACT_CMD = os.getenv("TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
DEVICE_ID = os.getenv("DEVICE_ID", "").strip()

SALAD_URL = os.getenv("SALAD_URL", "").rstrip("/")
SALAD_API_KEY = os.getenv("SALAD_API_KEY", "").strip()
SALAD_MODEL = os.getenv("SALAD_MODEL", "Qwen/Qwen2.5-VL-7B-Instruct")
SALAD_ORGANIZATION = os.getenv("SALAD_ORGANIZATION", "").strip()
SALAD_STORAGE_URL = os.getenv("SALAD_STORAGE_URL", "https://storage-api.salad.com").rstrip("/")
VISION_TRANSPORT = os.getenv("VISION_TRANSPORT", "salad_s4").strip().lower()
S4_SIGNED_URL_TTL = int(os.getenv("S4_SIGNED_URL_TTL", "600"))
S4_DELETE_AFTER_INFERENCE = os.getenv("S4_DELETE_AFTER_INFERENCE", "true").strip().lower() in {"1", "true", "yes", "on"}

SCREENSHOT_DIR = Path(os.getenv("SCREENSHOT_DIR", str(BASE_DIR / "screenshots")))
DEBUG_LOG_FILE = Path(os.getenv("DEBUG_LOG_FILE", str(BASE_DIR / "debug_runner.log")))
ACTION_LOG_FILE = Path(os.getenv("ACTION_LOG_FILE", str(BASE_DIR / "automation_log.csv")))
KB_FILE = Path(os.getenv("KB_FILE", str(BASE_DIR / "knowledge_base.json")))
PERSONA_FILE = Path(os.getenv("PERSONA_FILE", str(BASE_DIR / "persona_data.py")))
SURVEY_PACKAGE = os.getenv("SURVEY_PACKAGE", "topsurveys.paid.survey.money.cash")
SURVEY_ACTIVITY = os.getenv("SURVEY_ACTIVITY", "topsurveys.paid.survey.money.cash/.MainActivity")
STATE_FILE = Path(os.getenv("STATE_FILE", str(BASE_DIR / "agent_state.json")))
SAVE_SCREEN_MAPS = os.getenv(
    "SAVE_SCREEN_MAPS", "true"
).strip().lower() in {"1", "true", "yes", "on"}

MAX_AGENT_STEPS = int(os.getenv("MAX_AGENT_STEPS", "200"))
MAX_ACTION_RETRIES = int(os.getenv("MAX_ACTION_RETRIES", "3"))
POST_ACTION_WAIT = float(os.getenv("POST_ACTION_WAIT", "0.7"))
REQUESTED_VISION_MAX_DIM = int(os.getenv("VISION_MAX_DIM", "1152"))
VISION_MAX_DIM = min(REQUESTED_VISION_MAX_DIM, 1152)
VISION_RETRY_MAX_DIM = min(int(os.getenv("VISION_RETRY_MAX_DIM", "1024")), 1024)
LLM_MAX_TOKENS = min(int(os.getenv("LLM_MAX_TOKENS", "700")), 900)
LLM_RETRY_MAX_TOKENS = min(int(os.getenv("LLM_RETRY_MAX_TOKENS", "500")), 700)
UI_ACTIONABLE_LIMIT = int(os.getenv("UI_ACTIONABLE_LIMIT", "30"))
UI_TEXT_LIMIT = int(os.getenv("UI_TEXT_LIMIT", "10"))
OCR_CHAR_LIMIT = int(os.getenv("OCR_CHAR_LIMIT", "2500"))
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "60"))
LOW_CONFIDENCE = float(os.getenv("LOW_CONFIDENCE", "0.55"))
ALLOW_PERSONAL_INFERENCE = os.getenv(
    "ALLOW_PERSONAL_INFERENCE", "true"
).strip().lower() in {"1", "true", "yes", "on"}
PERSIST_INFERRED_ANSWERS = os.getenv(
    "PERSIST_INFERRED_ANSWERS", "true"
).strip().lower() in {"1", "true", "yes", "on"}
ALLOW_INTERACTIVE_HUMAN_INPUT = os.getenv(
    "ALLOW_INTERACTIVE_HUMAN_INPUT", "true"
).strip().lower() in {"1", "true", "yes", "on"}
HUMAN_INPUT_MAX_ATTEMPTS = max(1, int(os.getenv("HUMAN_INPUT_MAX_ATTEMPTS", "3")))
MAX_STAGNATION_CYCLES = int(os.getenv("MAX_STAGNATION_CYCLES", "4"))
MAX_STAGNATION_VLM_TRIES = max(1, int(os.getenv("MAX_STAGNATION_VLM_TRIES", "3")))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_BASE_URL = os.getenv(
    "GEMINI_BASE_URL",
    "https://generativelanguage.googleapis.com/v1beta/openai",
).rstrip("/")
GEMINI_LITE_MODEL = os.getenv("GEMINI_LITE_MODEL", "gemini-3.5-flash-lite")
GEMINI_FLASH_MODEL = os.getenv("GEMINI_FLASH_MODEL", "gemini-3.6-flash")
GEMINI_LITE_FALLBACKS = ("gemini-3.5-flash-lite", "gemini-2.5-flash-lite")
GEMINI_FLASH_FALLBACKS = ("gemini-3.6-flash", "gemini-3.5-flash", "gemini-2.5-flash")
GEMINI_LIVE_LITE = ("gemini-3.5-flash-lite",)
GEMINI_LIVE_FLASH = ("gemini-3.6-flash", "gemini-3.5-flash")
GEMINI_RETIRED_MODELS = {"gemini-2.5-flash-lite", "gemini-2.5-flash"}
VLM_PRIMARY = os.getenv("VLM_PRIMARY", "salad").strip().lower()
VLM_HOURLY_BUDGET_USD = float(os.getenv("VLM_HOURLY_BUDGET_USD", "0.30"))
SURVEY_SELECTION_POLICY = os.getenv(
    "SURVEY_SELECTION_POLICY", "highest_value"
).strip().lower()
COOKIE_CONSENT_ACTION = os.getenv(
    "COOKIE_CONSENT_ACTION", "accept"
).strip().lower()
if COOKIE_CONSENT_ACTION not in {"accept", "reject"}:
    COOKIE_CONSENT_ACTION = "accept"
WEBCAM_INTERVIEW_WILLING = os.getenv(
    "WEBCAM_INTERVIEW_WILLING", "true"
).strip().lower() in {"1", "true", "yes", "on"}
LEARNED_ACTION_MIN_CONFIDENCE = max(
    LOW_CONFIDENCE,
    min(0.99, float(os.getenv("LEARNED_ACTION_MIN_CONFIDENCE", "0.80"))),
)
MAX_LEARNED_SCREEN_ACTIONS = int(os.getenv("MAX_LEARNED_SCREEN_ACTIONS", "100"))
PERMISSION_POLICY = os.getenv("PERMISSION_POLICY", "safe_only").strip().lower()
ALLOW_CAMERA_PERMISSION = os.getenv("ALLOW_CAMERA_PERMISSION", "false").strip().lower() in {"1", "true", "yes", "on"}
ALLOW_MICROPHONE_PERMISSION = os.getenv("ALLOW_MICROPHONE_PERMISSION", "false").strip().lower() in {"1", "true", "yes", "on"}
ALLOW_LOCATION_PERMISSION = os.getenv("ALLOW_LOCATION_PERMISSION", "false").strip().lower() in {"1", "true", "yes", "on"}
ALLOW_FILES_PERMISSION = os.getenv("ALLOW_FILES_PERMISSION", "false").strip().lower() in {"1", "true", "yes", "on"}
AUTHORIZED_UPLOAD_FILE = os.getenv("AUTHORIZED_UPLOAD_FILE", "").strip()

pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

logger = logging.getLogger("SurveyAutomation")
logger.setLevel(logging.INFO)
