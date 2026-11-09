import test from "node:test";
import assert from "node:assert/strict";
import { fontStack, langAttr, nfc, parseAllowUnverified } from "./languages.ts";

test("langAttr takes the primary subtag", () => {
  assert.equal(langAttr("hi-IN"), "hi");
  assert.equal(langAttr("ta-IN"), "ta");
  assert.equal(langAttr(null), undefined);
  assert.equal(langAttr(""), undefined);
});

test("fontStack uses font_family from languages.json, then Noto Sans", () => {
  const stack = fontStack({ font_family: "Noto Sans Tamil" });
  assert.ok(stack.startsWith('"Noto Sans Tamil", "Noto Sans"'));
  assert.ok(fontStack(undefined).startsWith('"Noto Sans"'));
});

test("nfc composes decomposed text and leaves composed text alone", () => {
  assert.equal(nfc("é"), "é");
  const hindi = "हिन्दी";
  assert.equal(nfc(hindi), hindi);
});

test("the dev switch only turns on for the string true", () => {
  assert.equal(parseAllowUnverified("true"), true);
  assert.equal(parseAllowUnverified(" TRUE "), true);
  assert.equal(parseAllowUnverified(undefined), false);
  assert.equal(parseAllowUnverified("1"), false);
});
