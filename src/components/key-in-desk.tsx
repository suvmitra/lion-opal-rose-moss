import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowUpRight,
  Check,
  CircleAlert,
  Keyboard,
  RotateCcw,
  Terminal,
} from "lucide-react";
import {
  deriveQuestionKbKey,
  fallbackKeywordsFromQuestion,
  parseHumanAnswerInput,
  PETS_OCR,
  PETS_OPTIONS,
  questionTextFromOcr,
} from "@/lib/human-answer";
import { SEED_KNOWLEDGE_BASE, type KnowledgeBase } from "@/lib/seed-kb";
import { cn } from "@/lib/utils";

type Phase = "waiting" | "ticking" | "advancing" | "done";
type LogKind = "llm" | "human" | "kb" | "tick" | "next";

type LogEntry = {
  id: number;
  kind: LogKind;
  text: string;
};

const INITIAL_LOG: LogEntry[] = [
  { id: 1, kind: "llm", text: "VLM returned no grounded action on this personal question." },
  { id: 2, kind: "human", text: "v24.0.16 would have exited. v24.0.17 is waiting for a keyed-in answer." },
];

const PRESETS = [
  { label: "Cat, Dog, Fish", value: "Cat, Dog, Fish" },
  { label: "only Fish", value: "only Fish" },
  { label: "none", value: "none" },
];

const QUESTION = questionTextFromOcr(PETS_OCR);
const KB_KEY = deriveQuestionKbKey(QUESTION);

function nowStamp() {
  return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function KeyInDesk() {
  const [input, setInput] = useState("");
  const [error, setError] = useState("");
  const [phase, setPhase] = useState<Phase>("waiting");
  const [checked, setChecked] = useState<string[]>([]);
  const [queue, setQueue] = useState<string[]>([]);
  const [kb, setKb] = useState<KnowledgeBase>({ ...SEED_KNOWLEDGE_BASE });
  const [log, setLog] = useState<LogEntry[]>([
    { id: 1, kind: "llm", at: nowStamp(), text: "VLM returned no grounded action on this personal question." },
    { id: 2, kind: "human", at: nowStamp(), text: "v24.0.16 would have exited. v24.0.17 is waiting for a keyed-in answer." },
  ]);
  const logId = useRef(2);
  const inputRef = useRef<HTMLInputElement>(null);

  const addLog = (kind: LogKind, text: string) => {
    logId.current += 1;
    setLog((current) => [...current, { id: logId.current, kind, text, at: nowStamp() }]);
  };

  useEffect(() => {
    if (phase !== "ticking" || queue.length === 0) return;
    const next = queue[0];
    const timer = window.setTimeout(() => {
      setChecked((current) => (current.includes(next) ? current : [...current, next]));
      addLog("tick", `select_option → ${next}`);
      const remaining = queue.slice(1);
      setQueue(remaining);
      if (remaining.length === 0) {
        setPhase("advancing");
      }
    }, 720);
    return () => window.clearTimeout(timer);
  }, [phase, queue]);

  useEffect(() => {
    if (phase !== "advancing") return;
    const timer = window.setTimeout(() => {
      addLog("next", "selection_complete — grounding Continue / Next on the following cycle.");
      setPhase("done");
    }, 900);
    return () => window.clearTimeout(timer);
  }, [phase]);

  const status = useMemo(() => {
    if (phase === "waiting") return { label: "Waiting for operator", tone: "warn" as const };
    if (phase === "ticking") return { label: `Ticking ${queue[0] ?? "options"}`, tone: "accent" as const };
    if (phase === "advancing") return { label: "Advancing", tone: "accent" as const };
    return { label: "Answer stored — continue", tone: "ok" as const };
  }, [phase, queue]);

  const submit = (raw: string) => {
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
    const nextKb: KnowledgeBase = {
      ...kb,
      household_pets: value,
      knowledge_base_version: "24.0.17",
      answer_metadata: {
        ...(typeof kb.answer_metadata === "object" ? kb.answer_metadata : {}),
        household_pets: {
          provenance: "declared",
          confidence: 1,
          question: QUESTION,
          source_basis: `Human terminal input: ${raw}`,
          updated_at_utc: new Date().toISOString().slice(0, 19) + "Z",
        },
      },
      personal_question_fallbacks: {
        household_pets: {
          kb_key: "household_pets",
          question_keywords: fallbackKeywordsFromQuestion(QUESTION),
          answer: value,
          provenance: "declared",
          confidence: 1,
        },
      },
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
    setLog([
      { id: 1, kind: "llm", at: nowStamp(), text: "VLM returned no grounded action on this personal question." },
      { id: 2, kind: "human", at: nowStamp(), text: "v24.0.16 would have exited. v24.0.17 is waiting for a keyed-in answer." },
    ]);
    inputRef.current?.focus();
  };

  return (
    <main className="min-h-dvh px-4 py-5 sm:px-6 sm:py-8 lg:px-10">
      <div className="mx-auto flex max-w-6xl flex-col gap-6">
        <header className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div className="max-w-xl">
            <p className="text-accent text-xs font-semibold tracking-[0.18em] uppercase">
              Survey runner · v24.0.17
            </p>
            <h1 className="font-display mt-2 text-4xl leading-tight tracking-tight text-ink sm:text-5xl">
              Key-In Desk
            </h1>
            <p className="text-muted mt-3 max-w-prose text-base leading-relaxed">
              When the model goes silent on a personal question, do not exit.
              Type the visible answers here. The runner writes{" "}
              <span className="text-ink font-medium">knowledge_base.json</span>{" "}
              and ticks every matching option before it continues.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <StatusChip label={status.label} tone={status.tone} />
            <a
              href="/releases/survey_with_salad.py"
              className="border-line text-ink inline-flex h-11 items-center gap-1.5 rounded-full border bg-surface px-4 text-sm font-medium shadow-[var(--shadow-border)] transition-transform duration-150 hover:-translate-y-px"
            >
              Download runner
              <ArrowUpRight className="size-4" />
            </a>
          </div>
        </header>

        <section className="grid items-start gap-5 lg:grid-cols-[minmax(0,0.92fr)_minmax(0,1.08fr)]">
          <PhoneSurvey checked={checked} ticking={queue[0] ?? null} done={phase === "done"} />
          <OperatorPanel
            input={input}
            error={error}
            phase={phase}
            kb={kb}
            log={log}
            inputRef={inputRef}
            onInput={setInput}
            onSubmit={() => submit(input)}
            onPreset={(value) => {
              setInput(value);
              submit(value);
            }}
            onReset={reset}
          />
        </section>
      </div>
    </main>
  );
}

function StatusChip({
  label,
  tone,
}: {
  label: string;
  tone: "warn" | "accent" | "ok";
}) {
  return (
    <span
      className={cn(
        "inline-flex h-11 items-center rounded-full px-4 text-sm font-medium",
        tone === "warn" && "bg-ink text-bg",
        tone === "accent" && "bg-accent text-accent-fg",
        tone === "ok" && "bg-ok text-bg",
      )}
    >
      {label}
    </span>
  );
}

function PhoneSurvey({
  checked,
  ticking,
  done,
}: {
  checked: string[];
  ticking: string | null;
  done: boolean;
}) {
  return (
    <div className="bg-surface rounded-xl p-3 shadow-[var(--shadow-border)]">
      <div className="flex items-center justify-between px-2 pb-2">
        <p className="text-faint text-xs font-medium tracking-[0.14em] uppercase">Device</p>
        <p className="text-muted text-xs">step_0005 · 50%</p>
      </div>
      <div className="rounded-lg bg-white outline outline-1 -outline-offset-1 outline-black/10">
        <div className="flex items-center justify-between px-4 py-3">
          <span className="text-ink text-lg leading-none">×</span>
          <span className="text-sm font-medium">Survey</span>
          <span className="text-muted text-lg leading-none">↻</span>
        </div>
        <div className="flex items-center gap-3 px-4 pb-3">
          <div className="bg-line h-2 flex-1 overflow-hidden rounded-full">
            <div className="bg-accent h-full w-1/2" />
          </div>
          <span className="text-muted text-xs tabular-nums">50%</span>
        </div>
        <div className="px-4 pb-4">
          <h2 className="text-[1.05rem] leading-snug font-medium">{QUESTION}</h2>
          <div className="border-line text-faint mt-4 flex h-11 items-center rounded-md border px-3 text-sm">
            Search
          </div>
          <ul className="mt-3 flex flex-col gap-2">
            {PETS_OPTIONS.map((option) => {
              const isChecked = checked.includes(option);
              const isNext = ticking === option;
              return (
                <li
                  key={option}
                  className={cn(
                    "flex min-h-14 items-center justify-between rounded-md px-3.5 py-2.5 transition-colors duration-200",
                    isChecked ? "bg-accent-soft" : "bg-bg",
                    isNext && "ring-accent ring-2",
                  )}
                >
                  <span className="pr-3 text-sm leading-snug">{option}</span>
                  <span
                    className={cn(
                      "flex size-6 shrink-0 items-center justify-center rounded-[5px] border transition-colors duration-200",
                      isChecked
                        ? "border-accent bg-accent text-accent-fg"
                        : "border-line bg-surface",
                    )}
                    aria-hidden="true"
                  >
                    {isChecked ? <Check className="size-3.5" strokeWidth={3} /> : null}
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
        <div className="border-line flex items-center justify-center border-t py-3">
          <span className={cn("text-sm font-medium", done ? "text-accent" : "text-accent/80")}>
            {done ? "Continue" : "Privacy Policy"}
          </span>
        </div>
      </div>
    </div>
  );
}

function OperatorPanel({
  input,
  error,
  phase,
  kb,
  log,
  inputRef,
  onInput,
  onSubmit,
  onPreset,
  onReset,
}: {
  input: string;
  error: string;
  phase: Phase;
  kb: KnowledgeBase;
  log: LogEntry[];
  inputRef: React.RefObject<HTMLInputElement | null>;
  onInput: (value: string) => void;
  onSubmit: () => void;
  onPreset: (value: string) => void;
  onReset: () => void;
}) {
  const locked = phase !== "waiting";
  const kbPreview = {
    household_pets: kb.household_pets ?? "(missing — key in to write)",
    answer_metadata: kb.answer_metadata ?? {},
    personal_question_fallbacks: kb.personal_question_fallbacks ?? {},
  };

  return (
    <div className="flex flex-col gap-4">
      <section className="bg-bg-ink rounded-xl p-4 text-bg shadow-[var(--shadow-border)] sm:p-5">
        <div className="mb-4 flex items-center gap-2">
          <Terminal className="size-4 text-accent-soft" />
          <h2 className="font-display text-xl text-bg">Operator terminal</h2>
        </div>
        <p className="text-bg/70 text-sm leading-relaxed">
          Question: {QUESTION}
        </p>
        <p className="text-bg/45 mt-2 font-mono text-xs">
          Visible options · 1 Amphibians · 2 Bird(s) · 3 Cat(s) · 4 Dog(s) · 5 Fish · 6 Horse(s) · 7 I do not have any pets
        </p>
        <form
          className="mt-4 flex flex-col gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            onSubmit();
          }}
        >
          <label className="text-bg/70 text-xs font-medium tracking-[0.14em] uppercase" htmlFor="answer">
            Answer
          </label>
          <div className="flex flex-col gap-2 sm:flex-row">
            <input
              id="answer"
              ref={inputRef}
              value={input}
              disabled={locked}
              placeholder="Cat, Dog, Fish"
              onChange={(event) => onInput(event.target.value)}
              className="h-12 min-h-12 flex-1 rounded-md bg-white/8 px-3 font-mono text-sm text-bg outline-none ring-1 ring-white/15 placeholder:text-bg/35 focus:ring-2 focus:ring-accent disabled:opacity-60"
            />
            <button
              type="submit"
              disabled={locked}
              className="bg-accent text-accent-fg inline-flex h-12 min-h-12 items-center justify-center gap-2 rounded-md px-5 text-sm font-semibold transition-transform duration-150 enabled:hover:-translate-y-px enabled:active:scale-[0.98] disabled:opacity-50"
            >
              <Keyboard className="size-4" />
              Key in
            </button>
          </div>
        </form>
        <div className="mt-3 flex flex-wrap gap-2">
          {PRESETS.map((preset) => (
            <button
              key={preset.value}
              type="button"
              disabled={locked}
              onClick={() => onPreset(preset.value)}
              className="h-10 rounded-full bg-white/8 px-3.5 text-sm text-bg/85 ring-1 ring-white/10 transition-colors duration-150 hover:bg-white/12 disabled:opacity-50"
            >
              {preset.label}
            </button>
          ))}
        </div>
        {error ? (
          <p className="mt-3 flex items-start gap-2 text-sm text-[#f0c7c2]">
            <CircleAlert className="mt-0.5 size-4 shrink-0" />
            {error}
          </p>
        ) : (
          <p className="text-bg/45 mt-3 text-sm">
            Commas, “only Fish”, numbered rows, or “none”. The runner never invents pets.
          </p>
        )}
      </section>

      <section className="bg-surface rounded-xl p-4 shadow-[var(--shadow-border)] sm:p-5">
        <div className="mb-3 flex items-center justify-between gap-3">
          <h2 className="font-display text-xl">Agent cycle</h2>
          <button
            type="button"
            onClick={onReset}
            className="text-muted hover:text-ink inline-flex h-10 items-center gap-1.5 rounded-full px-3 text-sm transition-colors"
          >
            <RotateCcw className="size-3.5" />
            Reset
          </button>
        </div>
        <ol className="flex max-h-48 flex-col gap-2 overflow-auto pr-1">
          {log.map((entry) => (
            <li key={entry.id} className="flex gap-3 text-sm leading-snug">
              <span className="text-faint w-20 shrink-0 font-mono text-xs tabular-nums">
                {entry.at}
              </span>
              <span
                className={cn(
                  "mt-0.5 w-12 shrink-0 text-[11px] font-semibold tracking-wide uppercase",
                  entry.kind === "llm" && "text-danger",
                  entry.kind === "human" && "text-accent",
                  entry.kind === "kb" && "text-ok",
                  entry.kind === "tick" && "text-ink",
                  entry.kind === "next" && "text-ok",
                )}
              >
                {entry.kind}
              </span>
              <span className="text-muted">{entry.text}</span>
            </li>
          ))}
        </ol>
      </section>

      <section className="bg-surface rounded-xl p-4 shadow-[var(--shadow-border)] sm:p-5">
        <h2 className="font-display text-xl">knowledge_base.json</h2>
        <p className="text-muted mt-1 text-sm">
          Key <span className="font-mono text-ink">{KB_KEY}</span> is written after a successful match, then reused on the next run.
        </p>
        <pre className="border-line mt-3 max-h-56 overflow-auto rounded-md border bg-bg p-3 font-mono text-[12px] leading-relaxed text-ink">
          {JSON.stringify(kbPreview, null, 2)}
        </pre>
        <div className="mt-4 flex flex-wrap gap-3 text-sm">
          <a className="text-accent inline-flex items-center gap-1 font-medium" href="/releases/human_answer_matching.py">
            Matching module
            <ArrowUpRight className="size-3.5" />
          </a>
          <a className="text-accent inline-flex items-center gap-1 font-medium" href="/releases/survey_with_salad.v24.0.16.py">
            Archived v24.0.16
            <ArrowUpRight className="size-3.5" />
          </a>
        </div>
      </section>
    </div>
  );
}
