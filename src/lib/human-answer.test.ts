import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  deriveQuestionKbKey,
  parseHumanAnswerInput,
  PETS_OCR,
  questionTextFromOcr,
  visibleAnswerOptionLabels,
} from "./human-answer.ts";

describe("human answer matching", () => {
  const options = visibleAnswerOptionLabels(PETS_OCR);
  const question = questionTextFromOcr(PETS_OCR);

  it("reads the pets household question and options", () => {
    assert.match(question.toLowerCase(), /pets currently live/);
    assert.ok(question.endsWith("?"));
    assert.deepEqual(
      ["Cat(s)", "Dog(s)", "Fish"].every((label) => options.includes(label)),
      true,
    );
    assert.equal(options.includes("Search"), false);
  });

  it("maps the question onto household_pets", () => {
    assert.equal(deriveQuestionKbKey(question), "household_pets");
  });

  it("parses Cat, Dog, Fish", () => {
    assert.deepEqual(parseHumanAnswerInput("Cat, Dog, Fish", options), {
      status: "ok",
      labels: ["Cat(s)", "Dog(s)", "Fish"],
    });
  });

  it("parses only Fish and none", () => {
    assert.deepEqual(parseHumanAnswerInput("only Fish", options), {
      status: "ok",
      labels: ["Fish"],
    });
    const none = parseHumanAnswerInput("none", options);
    assert.equal(none.status, "ok");
    assert.match(none.labels[0] ?? "", /pets/i);
  });

  it("parses numbered options and skip", () => {
    assert.deepEqual(parseHumanAnswerInput("3, 4, 5", options), {
      status: "ok",
      labels: ["Cat(s)", "Dog(s)", "Fish"],
    });
    assert.equal(parseHumanAnswerInput("skip", options).status, "skip");
  });
});
