import { i as __toESM } from "../_runtime.mjs";
import { L as require_react, v as require_jsx_runtime } from "../_libs/@tanstack/react-router+[...].mjs";
import { a as CircleAlert, i as Keyboard, n as Terminal, o as Check, r as RotateCcw, s as ArrowUpRight } from "../_libs/lucide-react.mjs";
import { t as clsx } from "../_libs/clsx.mjs";
import { t as twMerge } from "../_libs/tailwind-merge.mjs";
//#region node_modules/.nitro/vite/services/ssr/assets/routes--JRhXkeS.js
var import_react = /* @__PURE__ */ __toESM(require_react());
var import_jsx_runtime = require_jsx_runtime();
var OPTION_CHROME_LABELS = /* @__PURE__ */ new Set([
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
	"reject"
]);
var QUESTION_KB_KEY_HINTS = [
	[["which of these pets"], "household_pets"],
	[["pets currently live"], "household_pets"],
	[["pets", "household"], "household_pets"],
	[["pets", "live with you"], "household_pets"]
];
var NONE_TOKENS = /* @__PURE__ */ new Set([
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
	"don't have any pets"
]);
var SKIP_TOKENS = /* @__PURE__ */ new Set([
	"skip",
	"quit",
	"abort",
	"exit",
	"cancel",
	"stop"
]);
var STOP_WORDS = /* @__PURE__ */ new Set([
	"which",
	"of",
	"these",
	"the",
	"a",
	"an",
	"to",
	"in",
	"your",
	"you",
	"with",
	"currently",
	"do",
	"does",
	"what",
	"is",
	"are",
	"for",
	"and",
	"or",
	"on",
	"at",
	"this",
	"that",
	"live"
]);
function normalizeSpace(value) {
	return String(value || "").replace(/’/g, "'").replace(/\s+/g, " ").trim();
}
function optionMatchKeys(label) {
	const text = normalizeSpace(label).toLowerCase();
	const keys = /* @__PURE__ */ new Set();
	if (!text) return keys;
	keys.add(text);
	keys.add(text.replace(/[^a-z0-9]+/g, ""));
	const stripped = normalizeSpace(text.replace(/\(s\)/gi, ""));
	if (stripped) {
		keys.add(stripped);
		if (!stripped.endsWith("s")) keys.add(`${stripped}s`);
		else keys.add(stripped.slice(0, -1));
	}
	for (const inner of text.match(/\(([^)]+)\)/g) ?? []) {
		const body = inner.slice(1, -1);
		for (const part of body.split(/[,/]| etc\.?/)) {
			const cleaned = normalizeSpace(part).replace(/^[. ]+|[. ]+$/g, "");
			if (cleaned && cleaned !== "s" && cleaned !== "etc") keys.add(cleaned);
		}
	}
	const stem = normalizeSpace((stripped || text).replace(/[^a-z0-9 ]+/g, " "));
	if (stem) {
		keys.add(stem);
		for (const word of stem.split(" ")) keys.add(word);
	}
	if (text.includes("do not have") || text.includes("don't have") || text.includes("no pets") || NONE_TOKENS.has(text)) for (const token of NONE_TOKENS) keys.add(token);
	keys.delete("");
	return keys;
}
function questionTextFromOcr(ocrText) {
	const pieces = [];
	for (const raw of String(ocrText || "").split(/\n/)) {
		const line = normalizeSpace(raw);
		if (!line) continue;
		const lowered = line.toLowerCase();
		if (OPTION_CHROME_LABELS.has(lowered)) {
			if (pieces.length) break;
			continue;
		}
		pieces.push(line);
		if (line.includes("?") || pieces.length >= 6) break;
	}
	let question = normalizeSpace(pieces.join(" "));
	const mark = question.lastIndexOf("?");
	if (mark >= 0) question = question.slice(0, mark + 1);
	return question;
}
function deriveQuestionKbKey(question, extraHints = {}) {
	const normalized = normalizeSpace(question).toLowerCase();
	for (const [hints, key] of QUESTION_KB_KEY_HINTS) if (hints.every((hint) => normalized.includes(hint))) return key;
	for (const [key, hints] of Object.entries(extraHints)) if (hints.some((hint) => normalized.includes(hint))) return key;
	return ((normalized.match(/[a-z0-9]+/g) ?? []).filter((word) => !STOP_WORDS.has(word)).slice(0, 6).join("_") || "survey_answer").replace(/[^a-z0-9_]+/g, "_").replace(/^_|_$/g, "");
}
function matchTokenToOptions(token, options) {
	const needle = normalizeSpace(token).toLowerCase();
	if (!needle) return null;
	if (/^\d+$/.test(needle)) {
		const index = Number(needle) - 1;
		return index >= 0 && index < options.length ? options[index] : null;
	}
	const needleKeys = optionMatchKeys(needle);
	const exact = [];
	const partial = [];
	for (const option of options) {
		const optionKeys = optionMatchKeys(option);
		const overlap = [...needleKeys].some((key) => optionKeys.has(key));
		if (optionKeys.has(needle) || option.toLowerCase() === needle || overlap) {
			exact.push(option);
			continue;
		}
		if (option.toLowerCase().includes(needle) || needle.includes(option.toLowerCase())) partial.push(option);
	}
	if (exact.length) return exact[0];
	if (partial.length === 1) return partial[0];
	return null;
}
function parseHumanAnswerInput(raw, options) {
	let text = normalizeSpace(raw);
	if (!text) return {
		status: "empty",
		labels: []
	};
	let lowered = text.toLowerCase();
	if (SKIP_TOKENS.has(lowered)) return {
		status: "skip",
		labels: []
	};
	const onlyMatch = text.match(/^only\s+(.+)$/i);
	if (onlyMatch) {
		text = normalizeSpace(onlyMatch[1]);
		lowered = text.toLowerCase();
	}
	if (NONE_TOKENS.has(lowered)) {
		const noneOption = options.find((option) => {
			const keys = optionMatchKeys(option);
			return [...NONE_TOKENS].some((token) => keys.has(token));
		});
		return noneOption ? {
			status: "ok",
			labels: [noneOption]
		} : {
			status: "unmatched",
			labels: []
		};
	}
	const tokens = text.split(/\s*(?:,|;|&|\band\b)\s*/).filter(Boolean);
	const matched = [];
	const seen = /* @__PURE__ */ new Set();
	for (const token of tokens.length ? tokens : [text]) {
		const option = matchTokenToOptions(token, options);
		if (!option) continue;
		const key = option.toLowerCase();
		if (seen.has(key)) continue;
		seen.add(key);
		matched.push(option);
	}
	return matched.length ? {
		status: "ok",
		labels: matched
	} : {
		status: "unmatched",
		labels: []
	};
}
function fallbackKeywordsFromQuestion(question) {
	const normalized = normalizeSpace(question).toLowerCase();
	if (normalized.includes("pets") && normalized.includes("household")) return ["pets currently live", "household"];
	const words = (normalized.match(/[a-z0-9]+/g) ?? []).filter((word) => !STOP_WORDS.has(word));
	const phrases = [];
	if (words.length >= 2) phrases.push(words.slice(0, 3).join(" "));
	if (words[0]) phrases.push(words[0]);
	return phrases.slice(0, 3);
}
var PETS_OCR = `Which of these pets currently live with you in your
household?
Search
Amphibians (frogs, toads, etc.)
Bird(s)
Cat(s)
Dog(s)
Fish
Horse(s)
I do not have any pets
Privacy Policy`;
var PETS_OPTIONS = [
	"Amphibians (frogs, toads, etc.)",
	"Bird(s)",
	"Cat(s)",
	"Dog(s)",
	"Fish",
	"Horse(s)",
	"I do not have any pets"
];
var SEED_KNOWLEDGE_BASE = {
	knowledge_base_version: "24.0.17",
	city: "Dublin",
	country: "Ireland",
	postal_code: "D22V048",
	area_code: "D22",
	employment_status: "Employed Full-Time",
	industry: "Information Technology",
	education: "Master's Degree",
	age_range: "40-45",
	has_children: "Yes",
	number_of_children: 1,
	child_gender: "Boy",
	child_age: 8,
	smoking_status: "No, I don't smoke",
	full_name: "Suvabrata Mitra",
	age: 44,
	gender: "Male",
	marital_status: "Married",
	flight_types: "Both domestic and international"
};
function cn(...inputs) {
	return twMerge(clsx(inputs));
}
var PRESETS = [
	{
		label: "Cat, Dog, Fish",
		value: "Cat, Dog, Fish"
	},
	{
		label: "only Fish",
		value: "only Fish"
	},
	{
		label: "none",
		value: "none"
	}
];
var QUESTION = questionTextFromOcr(PETS_OCR);
var KB_KEY = deriveQuestionKbKey(QUESTION);
function nowStamp() {
	return (/* @__PURE__ */ new Date()).toLocaleTimeString([], {
		hour: "2-digit",
		minute: "2-digit",
		second: "2-digit"
	});
}
function KeyInDesk() {
	const [input, setInput] = (0, import_react.useState)("");
	const [error, setError] = (0, import_react.useState)("");
	const [phase, setPhase] = (0, import_react.useState)("waiting");
	const [checked, setChecked] = (0, import_react.useState)([]);
	const [queue, setQueue] = (0, import_react.useState)([]);
	const [kb, setKb] = (0, import_react.useState)({ ...SEED_KNOWLEDGE_BASE });
	const [log, setLog] = (0, import_react.useState)([{
		id: 1,
		kind: "llm",
		at: nowStamp(),
		text: "VLM returned no grounded action on this personal question."
	}, {
		id: 2,
		kind: "human",
		at: nowStamp(),
		text: "v24.0.16 would have exited. v24.0.17 is waiting for a keyed-in answer."
	}]);
	const logId = (0, import_react.useRef)(2);
	const inputRef = (0, import_react.useRef)(null);
	const addLog = (kind, text) => {
		logId.current += 1;
		setLog((current) => [...current, {
			id: logId.current,
			kind,
			text,
			at: nowStamp()
		}]);
	};
	(0, import_react.useEffect)(() => {
		if (phase !== "ticking" || queue.length === 0) return;
		const next = queue[0];
		const timer = window.setTimeout(() => {
			setChecked((current) => current.includes(next) ? current : [...current, next]);
			addLog("tick", `select_option → ${next}`);
			const remaining = queue.slice(1);
			setQueue(remaining);
			if (remaining.length === 0) setPhase("advancing");
		}, 720);
		return () => window.clearTimeout(timer);
	}, [phase, queue]);
	(0, import_react.useEffect)(() => {
		if (phase !== "advancing") return;
		const timer = window.setTimeout(() => {
			addLog("next", "selection_complete — grounding Continue / Next on the following cycle.");
			setPhase("done");
		}, 900);
		return () => window.clearTimeout(timer);
	}, [phase]);
	const status = (0, import_react.useMemo)(() => {
		if (phase === "waiting") return {
			label: "Waiting for operator",
			tone: "warn"
		};
		if (phase === "ticking") return {
			label: `Ticking ${queue[0] ?? "options"}`,
			tone: "accent"
		};
		if (phase === "advancing") return {
			label: "Advancing",
			tone: "accent"
		};
		return {
			label: "Answer stored — continue",
			tone: "ok"
		};
	}, [phase, queue]);
	const submit = (raw) => {
		if (phase !== "waiting") return;
		const parsed = parseHumanAnswerInput(raw, PETS_OPTIONS);
		if (parsed.status === "empty") {
			setError("Type an answer, or pick one of the examples.");
			return;
		}
		if (parsed.status === "skip") {
			setError("Skip still halts this screen. Key a visible option instead.");
			return;
		}
		if (parsed.status !== "ok") {
			setError(`Could not match “${raw}” to a visible option.`);
			return;
		}
		setError("");
		const value = parsed.labels.length === 1 ? parsed.labels[0] : parsed.labels;
		const nextKb = {
			...kb,
			household_pets: value,
			knowledge_base_version: "24.0.17",
			answer_metadata: {
				...typeof kb.answer_metadata === "object" ? kb.answer_metadata : {},
				household_pets: {
					provenance: "declared",
					confidence: 1,
					question: QUESTION,
					source_basis: `Human terminal input: ${raw}`,
					updated_at_utc: (/* @__PURE__ */ new Date()).toISOString().slice(0, 19) + "Z"
				}
			},
			personal_question_fallbacks: { household_pets: {
				kb_key: "household_pets",
				question_keywords: fallbackKeywordsFromQuestion(QUESTION),
				answer: value,
				provenance: "declared",
				confidence: 1
			} }
		};
		setKb(nextKb);
		addLog("human", `Answer> ${raw}`);
		addLog("kb", `Wrote knowledge_base.json:${KB_KEY} = ${JSON.stringify(value)}`);
		setChecked([]);
		setQueue(parsed.labels);
		setPhase("ticking");
	};
	const reset = () => {
		setInput("");
		setError("");
		setPhase("waiting");
		setChecked([]);
		setQueue([]);
		setKb({ ...SEED_KNOWLEDGE_BASE });
		logId.current = 2;
		setLog([{
			id: 1,
			kind: "llm",
			at: nowStamp(),
			text: "VLM returned no grounded action on this personal question."
		}, {
			id: 2,
			kind: "human",
			at: nowStamp(),
			text: "v24.0.16 would have exited. v24.0.17 is waiting for a keyed-in answer."
		}]);
		inputRef.current?.focus();
	};
	return /* @__PURE__ */ (0, import_jsx_runtime.jsx)("main", {
		className: "min-h-dvh px-4 py-5 sm:px-6 sm:py-8 lg:px-10",
		children: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
			className: "mx-auto flex max-w-6xl flex-col gap-6",
			children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("header", {
				className: "flex flex-col gap-4 md:flex-row md:items-end md:justify-between",
				children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
					className: "max-w-xl",
					children: [
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
							className: "text-accent text-xs font-semibold tracking-[0.18em] uppercase",
							children: "Survey runner · v24.0.17"
						}),
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)("h1", {
							className: "font-display mt-2 text-4xl leading-tight tracking-tight text-ink sm:text-5xl",
							children: "Key-In Desk"
						}),
						/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("p", {
							className: "text-muted mt-3 max-w-prose text-base leading-relaxed",
							children: [
								"When the model goes silent on a personal question, do not exit. Type the visible answers here. The runner writes",
								" ",
								/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
									className: "text-ink font-medium",
									children: "knowledge_base.json"
								}),
								" ",
								"and ticks every matching option before it continues."
							]
						})
					]
				}), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
					className: "flex flex-wrap items-center gap-2",
					children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(StatusChip, {
						label: status.label,
						tone: status.tone
					}), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("a", {
						href: "/releases/survey_with_salad.py",
						className: "border-line text-ink inline-flex h-11 items-center gap-1.5 rounded-full border bg-surface px-4 text-sm font-medium shadow-[var(--shadow-border)] transition-transform duration-150 hover:-translate-y-px",
						children: ["Download runner", /* @__PURE__ */ (0, import_jsx_runtime.jsx)(ArrowUpRight, { className: "size-4" })]
					})]
				})]
			}), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("section", {
				className: "grid items-start gap-5 lg:grid-cols-[minmax(0,0.92fr)_minmax(0,1.08fr)]",
				children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(PhoneSurvey, {
					checked,
					ticking: queue[0] ?? null,
					done: phase === "done"
				}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)(OperatorPanel, {
					input,
					error,
					phase,
					kb,
					log,
					inputRef,
					onInput: setInput,
					onSubmit: () => submit(input),
					onPreset: (value) => {
						setInput(value);
						submit(value);
					},
					onReset: reset
				})]
			})]
		})
	});
}
function StatusChip({ label, tone }) {
	return /* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
		className: cn("inline-flex h-11 items-center rounded-full px-4 text-sm font-medium", tone === "warn" && "bg-ink text-bg", tone === "accent" && "bg-accent text-accent-fg", tone === "ok" && "bg-ok text-bg"),
		children: label
	});
}
function PhoneSurvey({ checked, ticking, done }) {
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
		className: "bg-surface rounded-xl p-3 shadow-[var(--shadow-border)]",
		children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
			className: "flex items-center justify-between px-2 pb-2",
			children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
				className: "text-faint text-xs font-medium tracking-[0.14em] uppercase",
				children: "Device"
			}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
				className: "text-muted text-xs",
				children: "step_0005 · 50%"
			})]
		}), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
			className: "rounded-lg bg-white outline outline-1 -outline-offset-1 outline-black/10",
			children: [
				/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
					className: "flex items-center justify-between px-4 py-3",
					children: [
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
							className: "text-ink text-lg leading-none",
							children: "×"
						}),
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
							className: "text-sm font-medium",
							children: "Survey"
						}),
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
							className: "text-muted text-lg leading-none",
							children: "↻"
						})
					]
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
					className: "flex items-center gap-3 px-4 pb-3",
					children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
						className: "bg-line h-2 flex-1 overflow-hidden rounded-full",
						children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", { className: "bg-accent h-full w-1/2" })
					}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
						className: "text-muted text-xs tabular-nums",
						children: "50%"
					})]
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
					className: "px-4 pb-4",
					children: [
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)("h2", {
							className: "text-[1.05rem] leading-snug font-medium",
							children: QUESTION
						}),
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
							className: "border-line text-faint mt-4 flex h-11 items-center rounded-md border px-3 text-sm",
							children: "Search"
						}),
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)("ul", {
							className: "mt-3 flex flex-col gap-2",
							children: PETS_OPTIONS.map((option) => {
								const isChecked = checked.includes(option);
								return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("li", {
									className: cn("flex min-h-14 items-center justify-between rounded-md px-3.5 py-2.5 transition-colors duration-200", isChecked ? "bg-accent-soft" : "bg-bg", ticking === option && "ring-accent ring-2"),
									children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
										className: "pr-3 text-sm leading-snug",
										children: option
									}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
										className: cn("flex size-6 shrink-0 items-center justify-center rounded-[5px] border transition-colors duration-200", isChecked ? "border-accent bg-accent text-accent-fg" : "border-line bg-surface"),
										"aria-hidden": "true",
										children: isChecked ? /* @__PURE__ */ (0, import_jsx_runtime.jsx)(Check, {
											className: "size-3.5",
											strokeWidth: 3
										}) : null
									})]
								}, option);
							})
						})
					]
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
					className: "border-line flex items-center justify-center border-t py-3",
					children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
						className: cn("text-sm font-medium", done ? "text-accent" : "text-accent/80"),
						children: done ? "Continue" : "Privacy Policy"
					})
				})
			]
		})]
	});
}
function OperatorPanel({ input, error, phase, kb, log, inputRef, onInput, onSubmit, onPreset, onReset }) {
	const locked = phase !== "waiting";
	const kbPreview = {
		household_pets: kb.household_pets ?? "(missing — key in to write)",
		answer_metadata: kb.answer_metadata ?? {},
		personal_question_fallbacks: kb.personal_question_fallbacks ?? {}
	};
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
		className: "flex flex-col gap-4",
		children: [
			/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("section", {
				className: "bg-bg-ink rounded-xl p-4 text-bg shadow-[var(--shadow-border)] sm:p-5",
				children: [
					/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
						className: "mb-4 flex items-center gap-2",
						children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Terminal, { className: "size-4 text-accent-soft" }), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("h2", {
							className: "font-display text-xl text-bg",
							children: "Operator terminal"
						})]
					}),
					/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("p", {
						className: "text-bg/70 text-sm leading-relaxed",
						children: ["Question: ", QUESTION]
					}),
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
						className: "text-bg/45 mt-2 font-mono text-xs",
						children: "Visible options · 1 Amphibians · 2 Bird(s) · 3 Cat(s) · 4 Dog(s) · 5 Fish · 6 Horse(s) · 7 I do not have any pets"
					}),
					/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("form", {
						className: "mt-4 flex flex-col gap-3",
						onSubmit: (event) => {
							event.preventDefault();
							onSubmit();
						},
						children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("label", {
							className: "text-bg/70 text-xs font-medium tracking-[0.14em] uppercase",
							htmlFor: "answer",
							children: "Answer"
						}), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
							className: "flex flex-col gap-2 sm:flex-row",
							children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("input", {
								id: "answer",
								ref: inputRef,
								value: input,
								disabled: locked,
								placeholder: "Cat, Dog, Fish",
								onChange: (event) => onInput(event.target.value),
								className: "h-12 min-h-12 flex-1 rounded-md bg-white/8 px-3 font-mono text-sm text-bg outline-none ring-1 ring-white/15 placeholder:text-bg/35 focus:ring-2 focus:ring-accent disabled:opacity-60"
							}), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("button", {
								type: "submit",
								disabled: locked,
								className: "bg-accent text-accent-fg inline-flex h-12 min-h-12 items-center justify-center gap-2 rounded-md px-5 text-sm font-semibold transition-transform duration-150 enabled:hover:-translate-y-px enabled:active:scale-[0.98] disabled:opacity-50",
								children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Keyboard, { className: "size-4" }), "Key in"]
							})]
						})]
					}),
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
						className: "mt-3 flex flex-wrap gap-2",
						children: PRESETS.map((preset) => /* @__PURE__ */ (0, import_jsx_runtime.jsx)("button", {
							type: "button",
							disabled: locked,
							onClick: () => onPreset(preset.value),
							className: "h-10 rounded-full bg-white/8 px-3.5 text-sm text-bg/85 ring-1 ring-white/10 transition-colors duration-150 hover:bg-white/12 disabled:opacity-50",
							children: preset.label
						}, preset.value))
					}),
					error ? /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("p", {
						className: "mt-3 flex items-start gap-2 text-sm text-[#f0c7c2]",
						children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(CircleAlert, { className: "mt-0.5 size-4 shrink-0" }), error]
					}) : /* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
						className: "text-bg/45 mt-3 text-sm",
						children: "Commas, “only Fish”, numbered rows, or “none”. The runner never invents pets."
					})
				]
			}),
			/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("section", {
				className: "bg-surface rounded-xl p-4 shadow-[var(--shadow-border)] sm:p-5",
				children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
					className: "mb-3 flex items-center justify-between gap-3",
					children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("h2", {
						className: "font-display text-xl",
						children: "Agent cycle"
					}), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("button", {
						type: "button",
						onClick: onReset,
						className: "text-muted hover:text-ink inline-flex h-10 items-center gap-1.5 rounded-full px-3 text-sm transition-colors",
						children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(RotateCcw, { className: "size-3.5" }), "Reset"]
					})]
				}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("ol", {
					className: "flex max-h-48 flex-col gap-2 overflow-auto pr-1",
					children: log.map((entry) => /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("li", {
						className: "flex gap-3 text-sm leading-snug",
						children: [
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
								className: "text-faint w-20 shrink-0 font-mono text-xs tabular-nums",
								children: entry.at
							}),
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
								className: cn("mt-0.5 w-12 shrink-0 text-[11px] font-semibold tracking-wide uppercase", entry.kind === "llm" && "text-danger", entry.kind === "human" && "text-accent", entry.kind === "kb" && "text-ok", entry.kind === "tick" && "text-ink", entry.kind === "next" && "text-ok"),
								children: entry.kind
							}),
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
								className: "text-muted",
								children: entry.text
							})
						]
					}, entry.id))
				})]
			}),
			/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("section", {
				className: "bg-surface rounded-xl p-4 shadow-[var(--shadow-border)] sm:p-5",
				children: [
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)("h2", {
						className: "font-display text-xl",
						children: "knowledge_base.json"
					}),
					/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("p", {
						className: "text-muted mt-1 text-sm",
						children: [
							"Key ",
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
								className: "font-mono text-ink",
								children: KB_KEY
							}),
							" is written after a successful match, then reused on the next run."
						]
					}),
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)("pre", {
						className: "border-line mt-3 max-h-56 overflow-auto rounded-md border bg-bg p-3 font-mono text-[12px] leading-relaxed text-ink",
						children: JSON.stringify(kbPreview, null, 2)
					}),
					/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
						className: "mt-4 flex flex-wrap gap-3 text-sm",
						children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("a", {
							className: "text-accent inline-flex items-center gap-1 font-medium",
							href: "/releases/human_answer_matching.py",
							children: ["Matching module", /* @__PURE__ */ (0, import_jsx_runtime.jsx)(ArrowUpRight, { className: "size-3.5" })]
						}), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("a", {
							className: "text-accent inline-flex items-center gap-1 font-medium",
							href: "/releases/survey_with_salad.v24.0.16.py",
							children: ["Archived v24.0.16", /* @__PURE__ */ (0, import_jsx_runtime.jsx)(ArrowUpRight, { className: "size-3.5" })]
						})]
					})
				]
			})
		]
	});
}
function Home() {
	return /* @__PURE__ */ (0, import_jsx_runtime.jsx)(KeyInDesk, {});
}
//#endregion
export { Home as component };
