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
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, "..");
const html = readFileSync(join(ROOT, "index.html"), "utf8");
const code = html.match(/<script>([\s\S]*?)<\/script>/)[1];

const data = Object.fromEntries(["boxes", "poses", "frames"].map(n =>
  [`data/${n}.json`, JSON.parse(readFileSync(join(ROOT, "data", n + ".json"), "utf8"))]));

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
    createElement: () => ({ style: {}, append: noop, set value(v) { this._v = v; },
                            get value() { return this._v; } }),
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

/* 2. The squeeze: the project notes measured Jax's stance at 66 px full and 18 px
      squeezed, off the live overlay.  Frame 5 of 7 is the one that is 66. */
set({ atk: "liu-kang", mv: "liu-kang/hikick", def: "jax", pose: "stance",
      fr: 4, dist: 80 });
let s = S();
check("jax stance frame 5 full width", s.hurtFull[2] - s.hurtFull[0], 66);
check("jax stance frame 5 tested width", s.hurt[2] - s.hurt[0], 18);

/* 3. The squeeze is centred on the SILHOUETTE, not the anchor, so it drifts
      with the limbs rather than sitting symmetrically about 0. */
check("tested column is not centred on the anchor",
      s.hurt[0] + s.hurt[2] === 2 * s.D, false);

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
console.log(`  INFO  liu-kang/hikick vs jax stance: connects from ${first} to ${last} px` +
            ` (dead zone 0..${first - 1})`);

/* 5. Reach is not range.  The record's front edge is where the BOX ends; the
      move keeps connecting past it because the victim has width. */
const front = val('byId["liu-kang/hikick"]').front;
check("connects past the record's front edge", last > front, true);
console.log(`        front edge ${front} px, still connects at ${last} px`);

/* 6. Every record the viewer can select must render without throwing, on a
      defender who is a different character (the mirroring path). */
let drawn = 0, broke = [];
for (const m of val("BOX").moves) {
  set({ atk: "liu-kang", mv: m.id, def: "kitana", pose: "stance", fr: 0, dist: 70 });
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
      set({ atk: "liu-kang", mv: "liu-kang/hikick", def: c.id, pose: lane,
            fr: i, dist: 70 });
      try { sandbox.draw(); poses++; } catch (e) {
        broke.push(`${c.id}/${lane}#${i}: ${e.message}`);
      }
    }
  }
}
check("every defender pose frame renders", broke.slice(0, 3), []);
console.log(`  INFO  ${poses} pose frames drawn without error`);

console.log(`\n${n - fails}/${n} checks passed`);
process.exit(fails ? 1 : 0);
