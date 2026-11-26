## What

<!-- One or two sentences: what this PR changes. -->

## Why

<!-- The problem it solves. Link an issue or breakage report if there is one. -->

## How I tested

- [ ] `python3 -m unittest discover -s tests` passes
- [ ] `claude plugin validate .` passes
- [ ] Tried on a real TV (model, Android version):

## Safety checklist

- [ ] Anything that changes the TV goes through `bin/tvkit`: plan, `confirm()`, `take_snapshot()`, `Batch.log()` so `tvkit undo` works
- [ ] New `data/packages.json` entries cite a source in `src` (breakage report, measured test or official docs)
- [ ] Speed claims are backed by `tvkit bench-compare` output
- [ ] No screenshots, serial numbers, IP addresses or other personal device data committed
