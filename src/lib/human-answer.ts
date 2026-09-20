export const OPTION_CHROME_LABELS = new Set([
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
]);

export const QUESTION_KB_KEY_HINTS: Array<[string[], string]> = [
  [["which of these pets"], "household_pets"],
  [["pets currently live"], "household_pets"],
  [["pets", "household"], "household_pets"],
  [["pets", "live with you"], "household_pets"],
];

export const NONE_TOKENS = new Set([
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
]);

export const SKIP_TOKENS = new Set(["skip", "quit", "abort", "exit", "cancel", "stop"]);

const STOP_WORDS = new Set([
  "which", "of", "these", "the", "a", "an", "to", "in", "your", "you",
  "with", "currently", "do", "does", "what", "is", "are", "for", "and",
  "or", "on", "at", "this", "that", "live",
]);

export function normalizeSpace(value: string): string {
  return String(value || "")
    .replace(/’/g, "'")
    .replace(/\s+/g, " ")
    .trim();
}

export function optionMatchKeys(label: string): Set<string> {
  const text = normalizeSpace(label).toLowerCase();
  const keys = new Set<string>();
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
  const noneLike =
    text.includes("do not have") ||
    text.includes("don't have") ||
    text.includes("no pets") ||
    NONE_TOKENS.has(text);
  if (noneLike) {
    for (const token of NONE_TOKENS) keys.add(token);
  }
  keys.delete("");
  return keys;
}

export function questionTextFromOcr(ocrText: string): string {
  const pieces: string[] = [];
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

export function visibleAnswerOptionLabels(
  ocrText: string,
  nodeLabels: string[] = [],
): string[] {
  const labels: string[] = [];
  const seen = new Set<string>();
  const question = questionTextFromOcr(ocrText).toLowerCase();

  const add = (raw: string) => {
    const label = normalizeSpace(raw);
    if (!label || label.length < 2) return;
    const key = label.toLowerCase();
    if (OPTION_CHROME_LABELS.has(key) || seen.has(key)) return;
    if (key.endsWith("%") || /^\d{1,2}:\d{2}$/.test(key)) return;
    if (label.includes("?")) return;
    if (question && (question.includes(key) || key.includes(question))) return;
    seen.add(key);
    labels.push(label);
  };

  for (const nodeLabel of nodeLabels) add(nodeLabel);

  let pastQuestion = false;
  for (const raw of String(ocrText || "").split(/\n/)) {
    const line = normalizeSpace(raw);
    if (!line) continue;
    const lowered = line.toLowerCase();
    if (!pastQuestion) {
      if (line.includes("?") || OPTION_CHROME_LABELS.has(lowered)) {
        pastQuestion = true;
      }
      continue;
    }
    if (OPTION_CHROME_LABELS.has(lowered)) continue;
    add(line);
  }
  return labels;
}

export function deriveQuestionKbKey(
  question: string,
  extraHints: Record<string, string[]> = {},
): string {
  const normalized = normalizeSpace(question).toLowerCase();
  for (const [hints, key] of QUESTION_KB_KEY_HINTS) {
    if (hints.every((hint) => normalized.includes(hint))) return key;
  }
  for (const [key, hints] of Object.entries(extraHints)) {
    if (hints.some((hint) => normalized.includes(hint))) return key;
  }
  const words = normalized.match(/[a-z0-9]+/g) ?? [];
  const kept = words.filter((word) => !STOP_WORDS.has(word)).slice(0, 6);
  return (kept.join("_") || "survey_answer").replace(/[^a-z0-9_]+/g, "_").replace(/^_|_$/g, "");
}

export function intendedOptionsFromKbValue(value: unknown): string[] {
  if (value == null || value === "") return [];
  if (Array.isArray(value)) {
    return value.map((item) => String(item).trim()).filter(Boolean);
  }
  const text = String(value).trim();
  if (/[,;]/.test(text)) {
    return text.split(/[,;]/).map((part) => part.trim()).filter(Boolean);
  }
  return [text];
}

function matchTokenToOptions(token: string, options: string[]): string | null {
  const needle = normalizeSpace(token).toLowerCase();
  if (!needle) return null;
  if (/^\d+$/.test(needle)) {
    const index = Number(needle) - 1;
    return index >= 0 && index < options.length ? options[index] : null;
  }
  const needleKeys = optionMatchKeys(needle);
  const exact: string[] = [];
  const partial: string[] = [];
  for (const option of options) {
    const optionKeys = optionMatchKeys(option);
    const overlap = [...needleKeys].some((key) => optionKeys.has(key));
    if (optionKeys.has(needle) || option.toLowerCase() === needle || overlap) {
      exact.push(option);
      continue;
    }
    if (option.toLowerCase().includes(needle) || needle.includes(option.toLowerCase())) {
      partial.push(option);
    }
  }
  if (exact.length) return exact[0];
  if (partial.length === 1) return partial[0];
  return null;
}

export type ParseStatus = "ok" | "skip" | "empty" | "unmatched";

export function parseHumanAnswerInput(
  raw: string,
  options: string[],
): { status: ParseStatus; labels: string[] } {
  let text = normalizeSpace(raw);
  if (!text) return { status: "empty", labels: [] };
  let lowered = text.toLowerCase();
  if (SKIP_TOKENS.has(lowered)) return { status: "skip", labels: [] };

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
    return noneOption ? { status: "ok", labels: [noneOption] } : { status: "unmatched", labels: [] };
  }

  const tokens = text.split(/\s*(?:,|;|&|\band\b)\s*/).filter(Boolean);
  const matched: string[] = [];
  const seen = new Set<string>();
  for (const token of tokens.length ? tokens : [text]) {
    const option = matchTokenToOptions(token, options);
    if (!option) continue;
    const key = option.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    matched.push(option);
  }
  return matched.length ? { status: "ok", labels: matched } : { status: "unmatched", labels: [] };
}

export function fallbackKeywordsFromQuestion(question: string): string[] {
  const normalized = normalizeSpace(question).toLowerCase();
  if (normalized.includes("pets") && normalized.includes("household")) {
    return ["pets currently live", "household"];
  }
  const words = (normalized.match(/[a-z0-9]+/g) ?? []).filter((word) => !STOP_WORDS.has(word));
  const phrases: string[] = [];
  if (words.length >= 2) phrases.push(words.slice(0, 3).join(" "));
  if (words[0]) phrases.push(words[0]);
  return phrases.slice(0, 3);
}

export const PETS_OCR = `Which of these pets currently live with you in your
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

export const PETS_OPTIONS = [
  "Amphibians (frogs, toads, etc.)",
  "Bird(s)",
  "Cat(s)",
  "Dog(s)",
  "Fish",
  "Horse(s)",
  "I do not have any pets",
];
