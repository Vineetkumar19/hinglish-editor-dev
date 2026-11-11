import test from "node:test";
import assert from "node:assert/strict";
import { wantsScreenContext } from "../src/screenIntent.js";

test("only direct screen inspection instructions imply capture", () => {
  for (const text of ["Look at my screen", "Cortana, what's on my screen?", "Please read this screen.", "meri screen dekho", "screen par kya hai", "मेरी स्क्रीन देखो", "इस स्क्रीन में क्या समस्या है"]) {
    assert.equal(wantsScreenContext(text), true, text);
  }
  for (const text of ["do not capture my screen", "don't look at my screen", "screen mat dekho", "स्क्रीन मत देखो", "How do I take a screenshot?", "Open screen recorder", "My screen is 16 inches", "Explain how screenshots work", "Can you look at my screen without capturing it?"]) {
    assert.equal(wantsScreenContext(text), false, text);
  }
});
