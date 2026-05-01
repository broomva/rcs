# helpers/ — agent-editable Python utilities

This is your scratchpad for code you find useful across tasks.

`starter.py` ships with a few stdlib utilities. Edit it, extend it, replace it
freely. Anything you write here is yours to use via `python -c "from helpers.starter import *"`
or by importing directly with `python -c "import sys; sys.path.insert(0,'helpers'); ..."`.

## Persistence

`helpers/` survives across episodes within a run.

The L2 meta-controller observes which edits recur across episodes. Recurring
helper edits become candidates for promotion into the next epoch's starter.
You don't need to do anything special — just keep editing usefully.
