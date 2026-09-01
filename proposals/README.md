# Proposals

One file here is one balance change, and one pull request.

The viewer writes these for you — open it, drag a number, say why, and press
**Open a pull request**. GitHub forks this repository to your account and opens
a new file with the proposal already in it. Commit, and it is a PR. You can
also write one by hand; it is four lines.

```json
{ "format": "boxlab-proposal", "format_version": 1,
  "base_digest": "9e142d8c362712f1",
  "why": "high kick whiffs at ranges where it visibly connects",
  "changes": [ { "id": "headband/hikick", "front": { "from": 94, "to": 91 } } ] }
```

## Why it is an overlay and not an edited file

"Just edit `data/boxes.json`" is the obvious alternative, and it does not work.

- That file is 228 records the generator owns. A browser that rewrites it
  reorders keys and reformats numbers, so the diff GitHub renders is thousands
  of lines of noise around the one that matters.
- Two people proposing two different moves both touch the same file, so they
  conflict for no reason.
- The file records the digest of the build it was read out of. A hand-edited
  copy still carries that digest while no longer matching it, which is worse
  than carrying none at all.

An overlay names the record, the field, the value it **expects to find** and
the value it **wants instead**. So it is small enough to read in the PR, it
cannot collide with anyone else's, and it fails loudly if the build moved
underneath it — because `from` no longer matches. That last one is the point:
a stale proposal is rejected by CI rather than silently applied to a number
that is no longer the number you measured against.

## What you can propose

`front`, `width`, `y`, `height`, `hit`, `block`.

Reactions are not proposable. They index a table of animations, so a "better"
value is not a bigger one, and neither the viewer nor the diff can show you
what you changed. Hurt boxes and frame timing are not proposable either, and
that is not an oversight — see [CONTRIBUTING.md](../CONTRIBUTING.md).

## What happens next

`tools/validate.py` checks shape and disclosure on your PR. `tools/apply.py`
prints what your change would do. Neither can tell you whether the change is
*good* — only a build can, and that happens on the maintainer's side, where the
overlay is applied, the game is rebuilt, and the boxes are drawn live over the
fighters. That screenshot comes back on the PR.

Applied proposals are deleted from this directory, because the data file then
carries the change and the overlay would be a duplicate of it.
