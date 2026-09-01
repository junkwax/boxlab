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
    for f in ("validate.py", "apply.py"):   # validate.py imports apply.py
        shutil.copy(os.path.join(HERE, f), os.path.join(tmp, "tools"))
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
    # INVENTED, not lifted. The checks match on SHAPE - a prefix and an
    # underscore - so a real symbol proves nothing a made-up one does not, and
    # using a real one would leave it sitting in a public repository. Still
    # split, because the whitelist has to reject it at runtime.
    edit(tmp, "boxes.json", lambda d: d["moves"][0].update(symbol="stk" "_notareal"))


@case("an artwork name", "UPPER CASE, no underscore - the one that got through")
def _(tmp):
    edit(tmp, "poses.json", lambda d: d["contacts"][0].update(art="NOTAN" "AME7"))


@case("a lane label", "a symbol arriving under an innocent key")
def _(tmp):
    edit(tmp, "poses.json", lambda d: d["contacts"][0].update(lane="a" "_notalane"))


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
    # An INVENTED name with the right shape. The pattern matches any stem, so
    # a real one proves nothing extra - and would leave a source filename
    # sitting in a public repository, which is the thing being tested for.
    write(tmp, "leak.md", "see the table in " "NOTAFILE." "ASM for the layout")


@case("a dangling move reference", "a proposal that renames a record")
def _(tmp):
    edit(tmp, "frames.json", lambda d: d["moves"][0].update(id="headband/invented"))


@case("a dangling pose reference", "a hand-edited pose list")
def _(tmp):
    edit(tmp, "poses.json", lambda d: d["contacts"][0].update(pose="p9999"))


@case("an out-of-range box", "a proposal with a typo'd extra digit")
def _(tmp):
    edit(tmp, "boxes.json", lambda d: d["moves"][0].update(front=9400))


@case("a duplicated record", "two people editing the same move")
def _(tmp):
    edit(tmp, "boxes.json", lambda d: d["moves"].append(dict(d["moves"][0])))


def propose(tmp, doc):
    """Drop a proposal into the scratch copy. See tools/apply.py."""
    os.makedirs(os.path.join(tmp, "proposals"), exist_ok=True)
    with open(os.path.join(tmp, "proposals", "p.json"), "w",
              encoding="utf-8") as fh:
        json.dump(doc, fh)


def a_real_record(tmp):
    """A record that exists, and a field a proposal is allowed to move."""
    with open(os.path.join(tmp, "data", "boxes.json"), encoding="utf-8") as fh:
        m = json.load(fh)["moves"][0]
    return m["id"], m["front"]


@case("a stale proposal", "the build moved under a pull request")
def _(tmp):
    rid, front = a_real_record(tmp)
    propose(tmp, {"format": "boxlab-proposal", "format_version": 1,
                  "why": "reads plausibly, and is measured against a build "
                         "that no longer exists",
                  "changes": [{"id": rid,
                               "front": {"from": front + 7, "to": front + 3}}]})


@case("a leak in a proposal", "the newest file anyone can add to this repo")
def _(tmp):
    rid, front = a_real_record(tmp)
    propose(tmp, {"format": "boxlab-proposal", "format_version": 1,
                  "why": "a legitimate reason, so the leak is not here",
                  "changes": [{"id": rid, "note": "a" "_notalane",
                               "front": {"from": front, "to": front + 3}}]})


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
