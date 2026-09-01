# Proposing a change

The data files in `data/` are not a description of the game's balance. They
*are* its balance: `data/boxes.json` is read back by the build and applied.
Change a number here, get it merged, and that is the number the game uses.

That is the reason this repository exists, and the reason the review is picky.

## The loop

**1. Change the box in the viewer.**

Open the viewer, pick the move, and **drag the box** — edges, corners, or the
middle to move it. Typing a number does the same thing if you already know the
value. Either way the proposed box is drawn in amber over the current one, so
you can see what you did before you argue for it.

Two things worth checking while you are there. The **play** button runs the
defender's pose at roughly the speed the game does, because an idle animation
breathes and the frame you happen to be parked on is not the whole story. And
the readout under the verdict says whether your change still connects **if they
duck** — a crouch is a different silhouette, not a modifier, and a move can
sail clean over it at a range where it plainly hits standing. You are not editing `data/boxes.json` — what you send is an
*overlay* naming the record, the field, the value it expects to find and the
value it wants instead. [proposals/README.md](proposals/README.md) says why.

The fields are named for what they do, because the game's own field names
mislead:

```json
{ "id": "headband/hikick", "table": "headband",
  "front": 94, "y": 5, "width": 69, "height": 23,
  "hit": 32, "block": 8, "hit_reaction": 0, "block_reaction": 0, "score": 0 }
```

| field | what it is |
|---|---|
| `front` | the **front edge** — how far the box reaches from the anchor. Bigger = more reach |
| `width` | extends **backwards** from `front`, toward the attacker. **Not** reach |
| `y` | the top edge, measured **down** from the anchor |
| `height` | downward from `y` |
| `hit` / `block` | damage on a clean hit, and chip damage on block. A full power bar is **161**, so the life bar at the top of the viewer shows what one hit removes and how many it takes to win |
| `hit_reaction` / `block_reaction` | which reaction the victim plays. **Not proposable** — it indexes a table of animations, so a "better" value is not a bigger one and nothing here can show you what you changed |

**`front` is where the box ends, not where the move lands.** The victim is cut
to a quarter of his width before the compare, so a move connects to roughly
`front + victim_width/8` and no further. A box widened by 20 px does not buy
20 px of range. Check it in the viewer before you argue for it.

**2. Press "Open a pull request".**

GitHub forks this repository to your account and opens a new file under
`proposals/` with your change already in it. Commit it, and it is a PR. If you
would rather not use the browser, press **Copy proposal** and add the file by
hand — it is four lines, and the format is documented.

To check it locally first:

```
python tools/validate.py     shape, disclosure, and your proposal
python tools/apply.py        what your proposal would change. Writes nothing
```

**3. Say what the numbers cannot.** The proposal already carries the record,
the field and both values, and CI prints them on the PR. Tell us the rest:

- **What changes** — which moves, in which direction.
- **Why** — the problem, stated as *behaviour*. "Big Arms' high kick whiffs at
  ranges where it visibly connects" is a reason. "`front` should be 96" is not.
- **How to see it** — the matchup, the spacing, and the input that shows it.

**4. CI checks shape and disclosure.** It cannot tell whether your change is
*good*. Nothing automated can.

**5. A maintainer applies and tests it.** The same file is imported into the
build, the game is rebuilt, and it goes through crash, behaviour and box
alignment checks with the boxes drawn live over the fighters. That screenshot
comes back on the PR — a hitbox argument settled with a picture of the hitbox
is settled; one settled with two people's memories is not.

**6. Merged changes are cited by digest.** "We played digest `9e142d8c`" is
checkable. "We played the version with the Headband fix" is not.

## What you cannot propose here, and why

| | |
|---|---|
| **hurt boxes** | not authored anywhere. They are computed from the sprite, so they change only when the artwork does. There is nothing to edit |
| **frame timing** | `data/frames.json` is currently read-only output. Timing lives in code, not a table, so it needs a different mechanism — it is the obvious next thing to build |
| **retail numbers** | `data/retail/` is a frozen reference, not a proposal target. If it is wrong it is a measurement bug; open an issue rather than a proposal |
| **inputs / motions** | same story, and likely the next pack after timing |
| **anything requiring new artwork** | out of scope for this repository entirely |

## Things reviewers will ask about

- **Shared records.** The three female ninjas read one strike table; the five
  ninjas read another. Editing one edits all of them. `tables` in
  `data/boxes.json` lists exactly who. Say whether that is what you intended.
- **Aliases.** Some records are several names over a single body. Editing any
  of them moves all of them. `aliases` names the others.
- **`base_digest`.** Your file records the build it was written against. If the
  build has moved since, that is visible, and the diff will say what it means.
- **Symmetry.** A change that helps one character in one matchup usually
  changes several others. Say which you checked.

## Reporting a problem instead

You do not need to propose a fix. An issue that says *this move whiffs at a
range where it obviously connects, here is the spacing* is a good issue, and
often a better one than a guessed number.
