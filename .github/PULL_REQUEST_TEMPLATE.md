<!--
The diff already shows WHAT changed. These are the three things it cannot show,
and a proposal without them cannot be reviewed - only argued about.
-->

### What changes

<!-- Which moves, in which direction. One line is fine. -->

### Why

<!-- State the problem as BEHAVIOUR, not as a number.

     good: "Big Arms' high kick whiffs at ranges where it visibly connects"
     bad:  "front should be 96"

     The second one might even be right, but nobody can check it. -->

### How to see it

<!-- The matchup, the spacing, and the input. Someone has to reproduce this on
     a build before it can be merged, and "it feels off" is not reproducible. -->

---

### Checklist

- [ ] `python tools/validate.py` passes locally
- [ ] I checked this in the viewer at the distances I am claiming
- [ ] I know whether this record is **shared** — the three female ninjas read
      one table, the five ninjas read another, and `tables` in
      `data/boxes.json` says who. Editing one edits all of them
- [ ] I know whether this record has **aliases** — several names over one body,
      all of which move together
- [ ] I have said which other matchups this affects, or that I checked and it
      affects none

<!-- Not required, and never held against you: if you are reporting a problem
     rather than proposing a number, open an issue instead. A well-described
     problem is often more useful than a guessed fix. -->
