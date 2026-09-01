#!/usr/bin/env python3
"""
validate.py - check this repository WITHOUT the game source.

That constraint is the whole design. A pull request from someone who has never
seen the game's source has to be checkable by CI that has never seen it either,
so this script imports nothing, downloads nothing, and reads only the files
next to it.

Three checks, which fail for different reasons:

  SHAPE       the data files are well formed, ids are unique and resolve to
              each other, numbers are in range. A broken proposal.

  DISCLOSURE  every string in every DATA file matches a pattern this project
              generates. A file that names something from the game's source -
              a routine, a label, a piece of artwork - fails here even if it
              is perfectly well formed.

  PROSE       the hand-written files - the viewer, the docs, these tools - do
              not name anything from the game's source either.

Disclosure is a WHITELIST, because data has a shape to whitelist. A blacklist
is a list of the leaks you thought of, and the one that got through first was
artwork names, which are upper case with no underscore and sail past any
"looks like a symbol" test.

Prose has no shape to whitelist, so it gets a blacklist. That is weaker, and
it is not a theoretical concern: the first draft of index.html named a routine
from the game's source in a code comment, and the first draft of THIS FILE
quoted a source filename in a test fixture. Both were written by someone who
had just finished building the whitelist. tools/prove_validator.py injects
each class of leak and proves this script rejects it - including a prose leak,
which was added after the prose patterns shipped broken and passed everything
for an afternoon.

  python tools/validate.py            check everything
  python tools/validate.py --quiet    print only failures
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")

# ------------------------------------------------------------- disclosure --
ID = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*(/[a-z0-9]+(-[a-z0-9]+)*)*$")
POSE = re.compile(r"^p[0-9]{4}$")
HEX = re.compile(r"^[0-9a-f]{7,40}$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
KEY = re.compile(r"^[a-z][a-z0-9_]*$")

NAMES = {"Kung Lao", "Liu Kang", "Johnny Cage", "Baraka", "Kitana", "Mileena",
         "Shang Tsung", "Raiden", "Sub-Zero", "Reptile", "Scorpion", "Jax",
         "Kintaro", "Shao Kahn", "Smoke", "Noob Saibot", "Jade"}
WORDS = {"mk2-hitbox-pack", "boxlab-pose-pack", "boxlab-frame-pack",
         "handler-name", "table", "assumed", "squeeze", "duck", ""}

# Free text we wrote. Allowed only under these keys, so a future edit cannot
# smuggle a borrowed sentence in under `id` or `character`.
PROSE_KEYS = {"title", "description", "units", "author"}


def disclosure(node, path, prose_ok=False, bad=None):
    if bad is None:
        bad = []
    if isinstance(node, dict):
        for k, v in node.items():
            if not (KEY.match(k) or ID.match(k) or POSE.match(k)):
                bad.append((path, "key %r" % k))
            disclosure(v, "%s.%s" % (path, k), k in PROSE_KEYS, bad)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            disclosure(v, "%s[%d]" % (path, i), prose_ok, bad)
    elif isinstance(node, str):
        s = node.strip()
        if prose_ok or s in NAMES or s in WORDS:
            return bad
        if not (ID.match(s) or POSE.match(s) or HEX.match(s) or DATE.match(s)):
            bad.append((path, s))
    return bad


# ------------------------------------------------------------ prose files --
TEXT_EXT = (".html", ".md", ".py", ".mjs", ".yml")

# The specific terms are SPLIT in this source - "sq" "_punch" - because a file
# that has to name them in order to find them would otherwise be the leak it is
# looking for. Python joins adjacent string literals at compile time, so the
# pattern is whole at runtime while the source line reads as two harmless
# fragments. The same trick is used in the test fixtures.
TERMS = ["sq" "_punch", "strike" "_check", "box" "_bounds", "mfra" "mew",
         "ani" "point", "stri" "ker", "ox" "pos", "oy" "pos", "fli" "ph",
         "multi" "part", "retract" "_strike"]

LEAKY = [
    (re.compile(r"\b[A-Za-z][A-Za-z0-9]*\.(?:ASM|TBL|GLO|HDR|IMG|IRW|LOD|BDB|BDD)\b"),
     "names a source or asset file"),
    (re.compile(r"\b(?:stk|scom|act|ani|mes|txt|sf|sc|ft|cb|aud|do|joy)_[a-z0-9_]+\b"),
     "looks like a symbol from the game's source"),
    (re.compile(r"\b(?:%s)\b" % "|".join(TERMS)),
     "a term from the game's source or toolchain"),
]

# An escape hatch for a line that genuinely has to contain one of these. It has
# never been needed - splitting the literal is always cleaner - but a check
# with no way out gets deleted the first time it is inconvenient.
EXEMPT = "validate-exempt"


def prose_files(errs):
    """The hand-written files, scanned for what a whitelist cannot see."""
    n = 0
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in (".git", "data")]
        for f in sorted(files):
            if not f.endswith(TEXT_EXT):
                continue
            path = os.path.join(base, f)
            rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
            n += 1
            with open(path, encoding="utf-8", errors="replace") as fh:
                for ln, line in enumerate(fh, 1):
                    if EXEMPT in line:
                        continue
                    for pat, why in LEAKY:
                        for hit in pat.finditer(line):
                            errs.append("%s:%d: %r %s"
                                        % (rel, ln, hit.group(0), why))
    return n


# ------------------------------------------------------------------ shape --
LIMITS = {"front": (-400, 400), "y": (-400, 400), "width": (0, 400),
          "height": (0, 400), "hit": (0, 255), "block": (0, 255),
          "hit_reaction": (0, 255), "block_reaction": (0, 255),
          "startup": (0, 400), "active": (0, 400), "recovery": (0, 400),
          "blockstun": (0, 400), "on_block": (-400, 400), "reach": (-400, 400)}


def load(name, errs):
    path = os.path.join(DATA, name)
    if not os.path.exists(path):
        errs.append("%s: missing" % name)
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as e:
        errs.append("%s: not valid JSON - %s" % (name, e))
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    errs, warns, notes = [], [], []

    boxes = load("boxes.json", errs)
    poses = load("poses.json", errs)
    frames = load("frames.json", errs)
    if errs:
        for e in errs:
            print("ERROR  %s" % e)
        return 1

    for name, doc, fmt in (("boxes.json", boxes, "mk2-hitbox-pack"),
                           ("poses.json", poses, "boxlab-pose-pack"),
                           ("frames.json", frames, "boxlab-frame-pack")):
        if doc.get("format") != fmt:
            errs.append("%s: format is %r, expected %r"
                        % (name, doc.get("format"), fmt))
        if doc.get("format_version", 1) != 1:
            errs.append("%s: format_version %r is not 1"
                        % (name, doc.get("format_version")))
        for where, what in disclosure(doc, name):
            errs.append("%s: %r is not a string this project generates (%s)"
                        % (name, what, where))

    notes.append("%d hand-written files scanned" % prose_files(errs))

    # -- boxes ------------------------------------------------------------
    move_ids, seen = set(), set()
    for i, m in enumerate(boxes.get("moves") or []):
        rid = m.get("id")
        if not rid:
            errs.append("boxes.json: move %d has no id" % (i + 1))
            continue
        if rid in seen:
            errs.append("boxes.json: %s is listed twice" % rid)
        seen.add(rid)
        move_ids.add(rid)
        for f, (lo, hi) in LIMITS.items():
            if f in m and isinstance(m[f], int) and not (lo <= m[f] <= hi):
                errs.append("boxes.json: %s.%s = %d is outside %d..%d"
                            % (rid, f, m[f], lo, hi))
        if m.get("width") == 0 or m.get("height") == 0:
            warns.append("boxes.json: %s has a zero-size box and can never "
                         "connect" % rid)
    if not move_ids:
        errs.append("boxes.json: no moves")
    notes.append("%d strike records" % len(move_ids))

    for rid in (boxes.get("flags") or {}):
        if rid not in move_ids:
            errs.append("boxes.json: flags name %s, which is not a record" % rid)

    # -- poses ------------------------------------------------------------
    chars = {c["id"] for c in (poses.get("characters") or []) if c.get("id")}
    if len(chars) != len(poses.get("characters") or []):
        errs.append("poses.json: duplicate character ids")
    notes.append("%d characters" % len(chars))

    pool = poses.get("poses") or {}
    for pid, rects in pool.items():
        if not POSE.match(pid):
            errs.append("poses.json: %r is not a pose id" % pid)
        if not isinstance(rects, list) or not rects:
            errs.append("poses.json: %s has no rectangles" % pid)
            continue
        for r in rects:
            if (not isinstance(r, list) or len(r) != 4
                    or not all(isinstance(v, int) for v in r)):
                errs.append("poses.json: %s has a malformed rectangle %r"
                            % (pid, r))
                break
            if r[2] <= 0 or r[3] <= 0:
                errs.append("poses.json: %s has a rectangle with no area %r"
                            % (pid, r))
                break
    notes.append("%d distinct poses" % len(pool))

    lanes = 0
    for cid, slots in (poses.get("stances") or {}).items():
        if cid not in chars:
            errs.append("poses.json: stances for %s, who is not a character" % cid)
        for slot, seq in slots.items():
            lanes += 1
            for pid in seq:
                if pid not in pool:
                    errs.append("poses.json: %s/%s references unknown pose %s"
                                % (cid, slot, pid))
    notes.append("%d defensive lanes" % lanes)

    for c in (poses.get("contacts") or []):
        if c.get("move") not in move_ids:
            errs.append("poses.json: contact for %r, which is not a record"
                        % c.get("move"))
        if c.get("character") not in chars:
            errs.append("poses.json: contact for %r, who is not a character"
                        % c.get("character"))
        if c.get("pose") not in pool:
            errs.append("poses.json: contact references unknown pose %r"
                        % c.get("pose"))
    notes.append("%d contact poses" % len(poses.get("contacts") or []))

    # -- frames -----------------------------------------------------------
    for m in (frames.get("moves") or []):
        if m.get("id") not in move_ids:
            errs.append("frames.json: timing for %r, which is not a record"
                        % m.get("id"))
        if m.get("character") not in chars:
            errs.append("frames.json: timing for %r, who is not a character"
                        % m.get("character"))
        for f, (lo, hi) in LIMITS.items():
            if f in m and isinstance(m[f], int) and not (lo <= m[f] <= hi):
                errs.append("frames.json: %s.%s = %d is outside %d..%d"
                            % (m.get("id"), f, m[f], lo, hi))
    notes.append("%d timed moves" % len(frames.get("moves") or []))

    # -- report -----------------------------------------------------------
    if not args.quiet:
        print("boxes  digest %s   built from %s"
              % (boxes.get("meta", {}).get("base_digest", "?"),
                 boxes.get("meta", {}).get("base_commit", "?")))
        print("poses  digest %s" % poses.get("meta", {}).get("digest", "?"))
        print("frames digest %s" % frames.get("meta", {}).get("digest", "?"))
        print("       " + ", ".join(notes))
        for w in warns:
            print("WARN   %s" % w)
    for e in errs:
        print("ERROR  %s" % e)

    if errs:
        print("\nFAILED - %d problem(s)." % len(errs))
        return 1
    if not args.quiet:
        print("\nOK - shape, disclosure and prose all clean.")
        print("CI cannot tell you whether a change is GOOD. Only a build can,")
        print("and that happens on the maintainer's side.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
