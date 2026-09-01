#!/usr/bin/env python3
"""
apply.py - fold proposals/*.json into data/boxes.json.

A proposal is an OVERLAY, never an edited copy of the data. That is the whole
design, and it is worth saying why, because "just edit the file" is the obvious
alternative and it does not work:

  * data/boxes.json is 228 records the generator owns. A browser that rewrites
    it reorders keys and reformats numbers, and the diff GitHub renders is then
    3,700 lines of noise around the one line that matters.
  * Two people proposing two different moves both touch the same file, so they
    conflict for no reason.
  * The file records the digest of the build it was read out of. A hand-edited
    copy still carries that digest while no longer matching it, which is worse
    than carrying none.

An overlay avoids all three. It names the record, the field, the value it
expects to find, and the value it wants instead - so it is small enough to read
in the PR, it cannot collide with anyone else's, and it FAILS LOUDLY if the
build moved underneath it, because `from` no longer matches.

  python tools/apply.py            say what would change, change nothing
  python tools/apply.py --write    apply, and delete the proposals applied
  python tools/apply.py --write --keep   apply, leave the files in place

After --write, regenerate boxes.json on the private side so its digest matches
the build again. This tool moves numbers; only a build makes them true.
"""
import argparse
import glob
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
PROPS = os.path.join(ROOT, "proposals")

# The fields a proposal is allowed to move. Reactions are deliberately absent:
# they index a table of animations, so a "better" value is not a bigger one and
# the viewer cannot show you what you changed.
FIELDS = {"front", "y", "width", "height", "hit", "block"}
LIMITS = {"front": (-400, 400), "y": (-400, 400), "width": (0, 400),
          "height": (0, 400), "hit": (0, 255), "block": (0, 255)}


def read(path):
    with io.open(path, encoding="utf-8") as fh:
        return json.load(fh)


def inspect(prop, name, boxes, errs):
    """Everything wrong with one proposal, as a list. Never raises."""
    n = len(errs)
    if prop.get("format") != "boxlab-proposal":
        errs.append("%s: format is %r, expected 'boxlab-proposal'"
                    % (name, prop.get("format")))
    if prop.get("format_version", 1) != 1:
        errs.append("%s: format_version %r is not 1"
                    % (name, prop.get("format_version")))
    if not (prop.get("why") or "").strip():
        errs.append("%s: no 'why'. State the problem as behaviour - a number "
                    "with no reason cannot be reviewed" % name)
    changes = prop.get("changes")
    if not isinstance(changes, list) or not changes:
        errs.append("%s: no changes" % name)
        return errs[n:]

    by_id = {m["id"]: m for m in boxes["moves"]}
    for i, c in enumerate(changes):
        where = "%s: change %d" % (name, i + 1)
        rid = c.get("id")
        rec = by_id.get(rid)
        if rec is None:
            errs.append("%s names %r, which is not a record" % (where, rid))
            continue
        moved = [k for k in c if k != "id"]
        if not moved:
            errs.append("%s (%s) moves no field" % (where, rid))
        for f in moved:
            if f not in FIELDS:
                errs.append("%s (%s) moves %r, which is not proposable. "
                            "Proposable: %s"
                            % (where, rid, f, ", ".join(sorted(FIELDS))))
                continue
            d = c[f]
            if not (isinstance(d, dict) and "from" in d and "to" in d):
                errs.append("%s (%s) %s must be {\"from\": n, \"to\": n}"
                            % (where, rid, f))
                continue
            if not all(isinstance(d[k], int) for k in ("from", "to")):
                errs.append("%s (%s) %s: from/to must be whole numbers"
                            % (where, rid, f))
                continue
            lo, hi = LIMITS[f]
            if not (lo <= d["to"] <= hi):
                errs.append("%s (%s) %s: %d is outside %d..%d"
                            % (where, rid, f, d["to"], lo, hi))
            if d["from"] == d["to"]:
                errs.append("%s (%s) %s: from and to are both %d, so this "
                            "proposes nothing" % (where, rid, f, d["from"]))
            if rec.get(f) != d["from"]:
                errs.append("%s (%s) %s: expects %r but the data says %r. The "
                            "build moved under this proposal - rebase it "
                            "against the current file"
                            % (where, rid, f, d["from"], rec.get(f)))
    return errs[n:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true",
                    help="actually modify data/boxes.json")
    ap.add_argument("--keep", action="store_true",
                    help="with --write, leave the proposal files in place")
    ap.add_argument("proposal", nargs="*",
                    help="specific files (default: proposals/*.json)")
    args = ap.parse_args()

    paths = args.proposal or sorted(glob.glob(os.path.join(PROPS, "*.json")))
    if not paths:
        print("No proposals to apply.")
        return 0

    boxes = read(os.path.join(DATA, "boxes.json"))
    digest = boxes.get("meta", {}).get("base_digest")
    errs, plan = [], []

    for path in paths:
        name = os.path.relpath(path, ROOT).replace(os.sep, "/")
        try:
            prop = read(path)
        except json.JSONDecodeError as e:
            errs.append("%s: not valid JSON - %s" % (name, e))
            continue
        bad = inspect(prop, name, boxes, errs)
        if prop.get("base_digest") and prop["base_digest"] != digest:
            print("NOTE   %s was written against %s, the data says %s"
                  % (name, prop["base_digest"], digest))
        if not bad:
            plan.append((name, prop))

    by_id = {m["id"]: m for m in boxes["moves"]}
    for name, prop in plan:
        print("\n%s" % name)
        print("  why: %s" % prop["why"].strip())
        for c in prop["changes"]:
            for f in (k for k in c if k != "id"):
                print("  %-28s %-8s %4d -> %4d"
                      % (c["id"], f, c[f]["from"], c[f]["to"]))
                if args.write:
                    by_id[c["id"]][f] = c[f]["to"]

    for e in errs:
        print("ERROR  %s" % e)
    if errs:
        print("\nFAILED - %d problem(s). Nothing was written." % len(errs))
        return 1

    if not args.write:
        print("\nDry run. Nothing written. Pass --write to apply.")
        return 0

    path = os.path.join(DATA, "boxes.json")
    with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(boxes, fh, indent=1, sort_keys=True, ensure_ascii=False)
        fh.write("\n")
    print("\nWrote data/boxes.json.")
    if not args.keep:
        for name, _ in plan:
            os.remove(os.path.join(ROOT, name))
        print("Removed %d applied proposal(s)." % len(plan))
    print("The digest now names a build this file no longer matches. "
          "Regenerate it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
