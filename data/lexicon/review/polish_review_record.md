# Review record: polish-round crop aliases (2026-11-18)

## What was reviewed

There are 130 crop aliases in `polish_crop_aliases.csv`: 74 Hindi and 56 Kannada, written in Latin letters ("gehu", "eerulli", "menasinakayi"). They were added to `data/lexicon/crops.csv` in `eded4fe`. When they were added:

- no alias collided with an existing crop;
- 15 names the draft proposed were already in the lexicon;
- ambiguous names were left out (for example, bare "gobhi" can mean cabbage or cauliflower).

## Who reviewed

1. **First review, under delegation.** The assistant (Claude) drafted and reviewed the list. The 130 rows in `crops.csv` are signed `Claude (delegated by Tarun, 2026-11-18)`, which is not the user's own signature. The Kannada rows were flagged for a native speaker's spot-check.
2. **The user's own check.** On 2026-11-18 Tarun, a Kannada speaker, read the transliterations and wrote in chat: *"I reviewed your transliterations, they are fine"*. Nothing was changed.

The row signatures stay as they are, because they record who drafted the rows and did the first review. This file records the user's check.

## Reversible

Each alias can be removed on its own row in `crops.csv`. The register is then rebuilt.
