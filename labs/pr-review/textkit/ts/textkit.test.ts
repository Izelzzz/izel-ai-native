import { test } from "node:test";
import assert from "node:assert/strict";

import { truncate, wordCount } from "./textkit.ts";

test("wordCount", () => {
  assert.equal(wordCount("hello brave new world"), 4);
  assert.equal(wordCount(""), 0);
});

test("truncate", () => {
  assert.equal(truncate("hello world", 8), "hello...");
  assert.equal(truncate("short", 10), "short");
  assert.throws(() => truncate("abc", 2), RangeError);
});
