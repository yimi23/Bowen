---
name: test-first-legacy
description: CAPTAIN's rule for touching existing code: characterize behavior with tests BEFORE changing it.
---

## The law (Feathers' rule, house edition)
Legacy code is code without tests. Before refactoring or extending it:
1. Write characterization tests that pin CURRENT behavior — including current bugs.
   Document a found bug in a test comment; do not silently fix it mid-refactor.
2. Run the suite after every file touched. Not after every phase — every file.
3. Only then change production code. The tests are the safety net, not the afterthought.
4. Mock every external service. A suite that needs the network is not a suite.
5. When the interface you are refactoring moves, the test assertions stay identical —
   only injection points change. If assertions must change, behavior changed: flag it.
