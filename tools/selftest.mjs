/*
 * selftest.mjs - run index.html's OWN javascript against the committed data,
 * with a stub DOM, and check the answers it gives.
 *
 * The point is that this exercises the shipped code rather than a second
 * implementation of the model that could agree with the page and both be
 * wrong.  It reads the <script> straight out of index.html.
 *
 *   node tools/selftest.mjs
 */
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, "..");
const html = readFileSync(join(ROOT, "index.html"), "utf8");
const code = html.match(/<script>([\s\S]*?)<\/script>/)[1];

const data = Object.fromEntries(["boxes", "poses", "frames"].map(n =>
  [`data/${n}.json`, JSON.parse(readFileSync(join(ROOT, "data", n + ".json"), "utf8"))]));

/* The retail reference is optional by design, so the stub serves it only when
   the repository actually carries one. Both paths get a check below. */
const RETAIL_PATH = join(ROOT, "data", "retail", "boxes.json");
const hasRetail = existsSync(RETAIL_PATH);
if (hasRetail)
  data["data/retail/boxes.json"] = JSON.parse(readFileSync(RETAIL_PATH, "utf8"));

/* ------------------------------------------------------------- stub DOM -- */
const els = {};
const noop = () => {};
function el(id) {
  if (els[id]) return els[id];
  const e = {
    id, value: "", textContent: "", innerHTML: "", checked: false,
    hidden: false, disabled: false, max: 0, min: 0, style: {},
    className: "", clientWidth: 1120,
    addEventListener: noop, append(c) { (this.kids ||= []).push(c); },
    getContext: () => new Proxy({}, {
      get: (_t, k) => (k === "canvas" ? {} :
        typeof k === "string" ? noop : undefined)
    }),
  };
  return (els[id] = e);
}
const sandbox = {
  document: {
    getElementById: el,
    createElement: (tag) => ({
      tag, style: {}, className: "", id: "", textContent: "", innerHTML: "",
      type: "", rows: 0, width: 0, height: 0, disabled: false, value: "",
      kids: [], append(c) { this.kids.push(c); }, addEventListener: noop,
      getContext: () => new Proxy({}, {
        get: (_t, k) => (k === "canvas" ? {} :
          typeof k === "string" ? noop : undefined)
      }),
    }),
  },
  fetch: async (u) => ({ ok: !!data[u], status: 200, json: async () => data[u] }),
  getComputedStyle: () => ({ getPropertyValue: () => "#000" }),
  devicePixelRatio: 1,
  addEventListener: noop,
  Math, JSON, Promise, console, Object, Array, Number, String, Error,
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
vm.runInContext(code, sandbox);

/* --------------------------------------------------------------- checks -- */
let fails = 0, n = 0;
const check = (what, got, want) => {
  n++;
  const ok = JSON.stringify(got) === JSON.stringify(want);
  if (!ok) fails++;
  console.log(`  ${ok ? "PASS" : "FAIL"}  ${what}` +
    (ok ? "" : `\n          got ${JSON.stringify(got)} want ${JSON.stringify(want)}`));
};

await new Promise(r => setTimeout(r, 60));   // let the fetch chain settle

const set = (o) => {
  for (const [k, v] of Object.entries(o)) el(k).value = String(v);
};
const S = () => sandbox.state();
const val = expr => vm.runInContext(expr, sandbox);

console.log("boxlab selftest — index.html's own model, against the committed data\n");

/* 1. The page loaded and wired itself up. */
check("controls are shown after load", el("controls").hidden, false);
check("attacker list is the full cast", el("atk").kids.length, 17);

/* 1b. init() ran to the END. Everything below this line tests the model; this
       line tests that the page finished building at all, which is the failure
       the stub used to hide. */
check("no load error was shown", el("err").style.display || "", "");
check("roster drew the whole cast", el("rcards").kids.length, 17);
check("retail overlay follows the file on disk",
      val("RETAIL") !== null, hasRetail);
if (hasRetail) {
  /* The mod widened this one from 96 to 120. If the two files ever stop
     disagreeing here, one of them was generated from the wrong tree. */
  set({ atk: "frosty", mv: "ninjas/ice1", def: "bigarms", pose: "stance",
        fr: 0, dist: 80 });
  const ice = S();
  check("retail box is read for a record the mod changed",
        ice.strikeRetail !== null, true);
  check("retail and current disagree where the mod moved the box",
        ice.strikeRetail[2] - ice.strikeRetail[0] !==
        ice.strike[2] - ice.strike[0], true);
  check("a record the mod did not touch has no ghost to draw",
        (() => { set({ atk: "headband", mv: "headband/hikick" });
                 const t = S();
                 return JSON.stringify(t.strike) ===
                        JSON.stringify(t.strikeRetail); })(), true);
}

/* 2. The squeeze: the project notes measured Big Arms' stance at 66 px full and
      18 px squeezed, off the live overlay.  Frame 5 of 7 is the one that is 66.

      THE 18 IS A RETAIL MEASUREMENT and this file asserted it long after the
      build stopped agreeing.  Both branches take a quarter of the width, but
      they truncate differently: retail leaves W - 2*((W>>3)+(W>>2)) = 18 on a
      66px silhouette, while the anchored branch is 2*(W>>3) = 16.  So the
      expected number depends on which model the pack declares, and hard-coding
      either one is how this test came to assert a build that was not shipping. */
const ANCHORED = val('(BOX.model || {}).column') === "anchor";
/* ...and how wide it is, which is a SEPARATE switch. Anchoring shipped
   with 2*(W>>3) = 16 on a 66px silhouette; `colwidth` recovers retail's
   own W - 2*((W>>3)+(W>>2)) = 18. Keying the expected number off the
   pack rather than hardcoding it is the whole point of `model`. */
const SHIFTW = val('(BOX.model || {}).column_width') !== "retail";
set({ atk: "headband", mv: "headband/hikick", def: "bigarms", pose: "stance",
      fr: 4, dist: 80 });
let s = S();
check("bigarms stance frame 5 full width", s.hurtFull[2] - s.hurtFull[0], 66);
check("bigarms stance frame 5 tested width", s.hurt[2] - s.hurt[0],
      (ANCHORED && SHIFTW) ? 16 : 18);

/* 3. Where that column sits is the whole difference between the two branches.
      Retail centres it on the SILHOUETTE, so it drifts with the limbs; the
      anchored branch centres it on the character's own anchor, so it does not.
      Assert whichever the pack says, rather than assuming. */
check(ANCHORED ? "tested column is centred on the anchor"
               : "tested column is not centred on the anchor",
      s.hurt[0] + s.hurt[2] === 2 * s.D, ANCHORED);

/* 4. Range is a BAND, not a threshold, and the near edge is the interesting
      one: standing on top of someone whiffs, because the box starts well in
      front of the attacker's own anchor. That is the documented point-blank
      dead zone, and a model that "connects at distance 0" would be wrong. */
const hits = [];
for (let d = 0; d <= 260; d++) { set({ dist: d }); hits.push(S().overlap); }
const first = hits.indexOf(true), last = hits.lastIndexOf(true);
const holes = hits.slice(first, last + 1).filter(v => !v).length;
check("the connecting range is one unbroken band", holes, 0);
check("whiffs point blank - the near dead zone is real", hits[0], false);
check("whiffs at 260 px", hits[260], false);
console.log(`  INFO  headband/hikick vs bigarms stance: connects from ${first} to ${last} px` +
            ` (dead zone 0..${first - 1})`);

/* 5. Reach is not range.  The record's front edge is where the BOX ends; the
      move keeps connecting past it because the victim has width. */
const front = val('byId["headband/hikick"]').front;
check("connects past the record's front edge", last > front, true);
console.log(`        front edge ${front} px, still connects at ${last} px`);

/* 6. Every record the viewer can select must render without throwing, on a
      defender who is a different character (the mirroring path). */
let drawn = 0, broke = [];
for (const m of val("BOX").moves) {
  set({ atk: "headband", mv: m.id, def: "knockout", pose: "stance", fr: 0, dist: 70 });
  try { sandbox.draw(); drawn++; } catch (e) { broke.push(m.id + ": " + e.message); }
}
check("every record renders", broke.slice(0, 3), []);
console.log(`  INFO  ${drawn} records drawn without error`);

/* 7. Every defender pose, every frame, for every character. */
let poses = 0;
for (const c of val("POSE").characters) {
  const lanes = val("POSE").stances[c.id] || {};
  for (const lane of Object.keys(lanes)) {
    for (let i = 0; i < lanes[lane].length; i++) {
      set({ atk: "headband", mv: "headband/hikick", def: c.id, pose: lane,
            fr: i, dist: 70 });
      try { sandbox.draw(); poses++; } catch (e) {
        broke.push(`${c.id}/${lane}#${i}: ${e.message}`);
      }
    }
  }
}
check("every defender pose frame renders", broke.slice(0, 3), []);
console.log(`  INFO  ${poses} pose frames drawn without error`);

/* 8. A proposal is the DIFFERENCE, never an edited copy of the record. The
      whole overlay design rests on this, and tools/apply.py reads back exactly
      what is asserted here. */
val('EDITS["headband/hikick"] = { front: 91 }');
const prop = val("proposal()");
check("proposal names the record", prop.changes[0].id, "headband/hikick");
check("proposal carries from and to", prop.changes[0].front, { from: 94, to: 91 });
check("proposal cites the digest it was written against",
      prop.base_digest, val("BOX.meta.base_digest"));
check("the loaded data is untouched by an edit",
      val('byId["headband/hikick"].front'), 94);

val('EDITS["headband/hikick"] = { front: 94 }');
check("an edit back to the shipped value proposes nothing",
      val("proposal()").changes.length, 0);
val('delete EDITS["headband/hikick"]');


/* 9. Dragging an edge. resize() is pure, so the geometry is checked here
      rather than by moving a mouse. left = front - width, right = front,
      top = y, bottom = y + height - and every handle has to respect that. */
const box = { front: 94, y: 5, width: 69, height: 23 };
check("dragging the right edge moves front and width together",
      val(`resize(${JSON.stringify(box)}, "r", -3, 0)`),
      { front: 91, y: 5, width: 66, height: 23 });
check("dragging the left edge changes width alone",
      val(`resize(${JSON.stringify(box)}, "l", 4, 0)`),
      { front: 94, y: 5, width: 65, height: 23 });
check("dragging the top edge holds the bottom still",
      val(`resize(${JSON.stringify(box)}, "t", 0, 6)`),
      { front: 94, y: 11, width: 69, height: 17 });
check("dragging the bottom edge changes height alone",
      val(`resize(${JSON.stringify(box)}, "b", 0, 5)`),
      { front: 94, y: 5, width: 69, height: 28 });
check("dragging the middle moves the box without resizing it",
      val(`resize(${JSON.stringify(box)}, "move", -8, 3)`),
      { front: 86, y: 8, width: 69, height: 23 });
check("a corner drives both axes",
      val(`resize(${JSON.stringify(box)}, "rb", 2, 2)`),
      { front: 96, y: 5, width: 71, height: 25 });
check("a box cannot be dragged to a negative width",
      val(`resize(${JSON.stringify(box)}, "l", 999, 0)`).width, 0);

/* 10. A drag reaches the proposal by the same road a typed number does. */
val('EDITS["headband/hikick"] = {}');
val(`(() => { const r = resize(byId["headband/hikick"], "r", -3, 0);
             for (const f of ["front","y","width","height"])
               setField("headband/hikick", f, r[f]); })()`);
check("a dragged edge becomes a proposal",
      val("proposal()").changes[0],
      { id: "headband/hikick", front: { from: 94, to: 91 },
        width: { from: 69, to: 66 } });
val('delete EDITS["headband/hikick"]');

/* 11. Ducking. A high punch that plainly connects on a standing opponent
       clears the crouch entirely - the silhouette drops below the box, which
       is why this is a different question from "is it shorter". */
set({ atk: "frosty", mv: "ninjas/hipunch", def: "bigarms", pose: "stance",
      fr: 0, dist: 70 });
const up = S();
check("the high punch connects standing at 70 px", up.overlap, true);
check("the crouch lane is read for every frame", up.duckHits.length, 3);
check("and it whiffs over the crouch on all of them",
      up.duckHits.some(Boolean), false);

/* A sweep is the other way round: flagged must-be-blocked-low, and ducking
   is no escape from it. */
set({ atk: "bigarms", mv: "bigarms/sweepk", def: "headband" });
check("a sweep is flagged must be blocked low", S().mustDuck, true);

/* 12. The two fighters have to read as two fighters. roleOf drives the canvas
       fill, the roster border and the thumbnail, so one check covers all
       three - and a mirror match resolves to the attacker rather than
       flickering between them. */
set({ atk: "headband", def: "bigarms" });
check("attacker, defender and bystander are three different roles",
      [val('roleOf("headband")'), val('roleOf("bigarms")'), val('roleOf("acid")')],
      ["--atk", "--body", "--dim"]);
set({ atk: "headband", def: "headband" });
check("a mirror match resolves to the attacker", val('roleOf("headband")'), "--atk");

/* 13. The life bar. 161 is the game's own full_strength, and hits-to-kill is a
       CEILING - 32 damage leaves a point standing after five, so the fifth hit
       does not win the round and the sixth does. Getting this wrong by one is
       the difference between a change that matters and one that does not. */
check("a full power bar is 161", val("FULL"), 161);
check("32 damage takes six hits, not five", val("toKill(32)"), 6);
check("  and five of them leave someone standing", 161 - 5 * 32 > 0, true);
check("the hardest hit in the game kills in three", val("toKill(64)"), 3);
check("one damage takes the whole bar", val("toKill(1)"), 161);
check("a record that does no damage never kills", val("toKill(0)"), null);

console.log(`\n${n - fails}/${n} checks passed`);
process.exit(fails ? 1 : 0);
