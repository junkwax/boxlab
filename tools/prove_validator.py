#!/usr/bin/env python3
"""
prove_validator.py - show that validate.py actually fails.

A check that has only ever passed is not a check.  This takes the committed
data, injects one fault at a time into a scratch copy, and asserts that
validate.py rejects each one.  If any injection sails through, THAT is the
bug - in the validator, not in the data.

The disclosure cases are the ones that matter, because each is a leak that a
plausible implementation misses:

  a source symbol      lower case with underscores - the obvious one
  an artwork name      UPPER CASE, no underscore - sails past every
                       "looks like a symbol" regex, and is exactly what got
                       through the first time this was attempted
  a lane label         looks like a symbol, arrives under a harmless key
  a borrowed sentence  free text under a key that is not a prose key
  a leak in the PROSE  the data files are not the only files in the repo, and
                       the pattern that scans the hand-written ones shipped
                       with a mangled escape: it matched nothing, reported
                       clean on every run, and was only caught by adding
                       these two cases

  python tools/prove_validator.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def run(tmp):
    """validate.py against a scratch copy.  Returns (exit code, output)."""
    r = subprocess.run([sys.executable, os.path.join(tmp, "tools", "validate.py")],
                       capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr)


def scratch():
    tmp = tempfile.mkdtemp(prefix="boxlab-prove-")
    os.makedirs(os.path.join(tmp, "tools"))
    shutil.copy(os.path.join(HERE, "validate.py"), os.path.join(tmp, "tools"))
    shutil.copytree(os.path.join(ROOT, "data"), os.path.join(tmp, "data"))
    return tmp


CASES = []


def case(name, why):
    def deco(fn):
        CASES.append((name, why, fn))
        return fn
    return deco


def write(tmp, fname, text):
    """Drop a hand-written file into the scratch copy, for the prose cases."""
    with open(os.path.join(tmp, fname), "w", encoding="utf-8") as fh:
        fh.write(text)


def edit(tmp, fname, fn):
    p = os.path.join(tmp, "data", fname)
    with open(p, encoding="utf-8") as fh:
        doc = json.load(fh)
    fn(doc)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(doc, fh)


@case("a source symbol", "the obvious leak")
def _(tmp):
    # Split the same way validate.py splits its own terms: the fixture has to
    # BE a leak at runtime without being one in the source.
    edit(tmp, "boxes.json", lambda d: d["moves"][0].update(symbol="stk" "_lkhikick"))


@case("an artwork name", "UPPER CASE, no underscore - the one that got through")
def _(tmp):
    edit(tmp, "poses.json", lambda d: d["contacts"][0].update(art="UGSW" "IPE3"))


@case("a lane label", "a symbol arriving under an innocent key")
def _(tmp):
    edit(tmp, "poses.json", lambda d: d["contacts"][0].update(lane="a" "_lkstance"))


@case("a borrowed sentence", "free text where free text does not belong")
def _(tmp):
    edit(tmp, "frames.json",
         lambda d: d["moves"][0].update(character="a sentence lifted from somewhere else"))


@case("a symbol in the PROSE", "the check that shipped broken and passed anyway")
def _(tmp):
    # These patterns were written with a mangled escape and matched NOTHING for
    # an afternoon, while reporting "clean" on every run. That is the exact
    # failure mode this whole file exists to prevent, so it gets a case.
    write(tmp, "leak.md", "the box is placed relative to the " "ani" "point")


@case("a source filename in the prose", "a doc that cites where it came from")
def _(tmp):
    write(tmp, "leak.md", "see the table in " "MKSTK." "ASM for the layout")


@case("a dangling move reference", "a proposal that renames a record")
def _(tmp):
    edit(tmp, "frames.json", lambda d: d["moves"][0].update(id="liu-kang/invented"))


@case("a dangling pose reference", "a hand-edited pose list")
def _(tmp):
    edit(tmp, "poses.json", lambda d: d["contacts"][0].update(pose="p9999"))


@case("an out-of-range box", "a proposal with a typo'd extra digit")
def _(tmp):
    edit(tmp, "boxes.json", lambda d: d["moves"][0].update(front=9400))


@case("a duplicated record", "two people editing the same move")
def _(tmp):
    edit(tmp, "boxes.json", lambda d: d["moves"].append(dict(d["moves"][0])))


def main():
    print("prove_validator - every one of these MUST be rejected\n")
    base = scratch()
    code, out = run(base)
    print("  %-24s %s" % ("unmodified data",
                          "accepted" if code == 0 else "REJECTED - wrong"))
    ok = (code == 0)
    shutil.rmtree(base, ignore_errors=True)
    if not ok:
        print("\nThe committed data does not validate. Fix that first.")
        print(out)
        return 1

    bad = 0
    for name, why, fn in CASES:
        tmp = scratch()
        try:
            fn(tmp)
            code, out = run(tmp)
            caught = code != 0
            if not caught:
                bad += 1
            print("  %-24s %s   (%s)"
                  % (name, "rejected" if caught else "SLIPPED THROUGH", why))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    print("\n%d/%d faults caught." % (len(CASES) - bad, len(CASES)))
    if bad:
        print("A leak that validate.py does not catch is a leak that ships.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
