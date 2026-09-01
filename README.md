# Boxlab

**What a 1993 arcade fighting game actually tests when you press a button.**

Open [the viewer](https://example.github.io/boxlab/), pick a move, and drag the
distance slider until it stops connecting. That is the whole idea.

This game has never had published hitbox data. What exists is scattered across
forum threads and a couple of PDFs, and none of it can show you *why* a move
that visibly overlaps an opponent does nothing. This can, because it draws the
model the game really uses instead of the picture a player sees.

> An unofficial fan project. Not affiliated with, endorsed by, or associated
> with Warner Bros. Entertainment Inc. or NetherRealm Studios. **No game code,
> artwork, audio or ROM data is distributed here.** See [NOTICE.md](NOTICE.md).

---

## The thing most people get wrong

The game does not test sprites against sprites. Per hit check, it does this:

1. **The strike box** — one rectangle, authored per move, held unchanged for
   the move's whole active window. Not per-frame. Not a shape. One rectangle.
2. **The hurt box** — *not authored anywhere*. It is computed live as the
   bounding box of every piece of the victim's current sprite.
3. **The squeeze** — that bounding box is then narrowed to **a quarter of its
   width**, centred on the silhouette. 204 of the 228 records do this.
4. **The compare** — a plain rectangle overlap. No per-piece test, no circles,
   no priority.

Three consequences that decide real matches, all of which you can reproduce in
the viewer in about ten seconds each:

- **Reach is not range.** A record's `front` is where the box *ends*, not where
  the move lands. Liu Kang's high kick has a front edge of 94 px and still
  connects at 109, because the victim has width. Widening a box by 20 px does
  not buy 20 px of range.
- **There is a dead zone at point blank.** That same kick connects from 24 px
  out. Stand closer than that and it passes straight through — the box starts
  in front of the attacker.
- **Idle animations breathe, and it matters.** Jax's stance swings between 60
  and 69 px wide across its seven frames. Which frame he is on changes the
  tested column by 3 px, and at the edge of a move's range that is the hit.

## No artwork, on purpose — and it is the *better* picture

There is no sprite here, and none is needed. Since the game tests rectangles,
rectangles are the honest drawing: the green outlines are the actual pieces the
sprite is assembled from, and the white box is the one the compare used. A
version of this with the artwork pasted in would look nicer and would hide the
only thing worth seeing, which is how little of a fighter is actually live.

That also keeps this repository clean. Every number here is a measurement.
Nothing in it is copied out of anyone's game.

## What is in here

| | |
|---|---|
| `index.html` | the viewer. One file, no build step, no dependencies |
| `data/boxes.json` | 228 strike records — box, damage, reactions, flags |
| `data/poses.json` | 869 poses as rectangles, plus which one each move is live on |
| `data/frames.json` | startup / active / recovery / advantage for 177 moves |
| `tools/validate.py` | shape + disclosure checks. Runs with no game source |
| `tools/prove_validator.py` | injects eight faults and proves each is rejected |
| `tools/selftest.mjs` | runs the viewer's own code against the data |

Run it locally:

```
python -m http.server        # then open http://localhost:8000/
python tools/validate.py
python tools/prove_validator.py
node   tools/selftest.mjs
```

Opening `index.html` straight off disk will not work — browsers block the data
files. Serve the folder.

## Where the numbers come from, and how good they are

Everything is read out of the game's own tables by a generator on the private
side, never typed in and never measured by eye. `data/boxes.json` is not a
description of the build — it is *the file the build reads back*, so the page
and the game cannot disagree. Each file carries a digest; the viewer shows it.

Known limits, stated rather than hidden:

- **Startup is missing for some moves.** Where a handler could not be resolved,
  the row is absent instead of estimated. A missing row costs you nothing; a
  wrong one costs you a match.
- **Contact poses carry a confidence.** `resolved by table` is trustworthy.
  `assumed` means the move was applied to every character because nothing in
  the data says who can reach it — verify before believing it.
- **Travelling moves and projectiles have no single contact pose** and are left
  out of the pose data rather than faked.
- **Hurt boxes are not authored, so they cannot be proposed.** They change only
  when the artwork changes.

## Proposing a change

The data files are the balance. Edit a number, open a pull request, and the
diff GitHub renders *is* the change — no tooling required to read it. See
[CONTRIBUTING.md](CONTRIBUTING.md).

CI checks that a proposal is well formed and discloses nothing it should not.
It cannot tell you whether a change is *good*. Only a build can, and that
happens on the maintainer's side, where the same file is applied to the game
and tested.
