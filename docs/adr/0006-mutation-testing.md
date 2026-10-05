# 0006. Gate quality with mutation testing, not line coverage alone

Status: Accepted

## Context
Line coverage shows which code ran during tests, not whether the tests would notice if that code were wrong. Mutation testing makes small changes to the source (flip a comparison, empty a string, drop a call) and checks that some test fails; the share of mutants killed is a better measure of test strength ([Stryker: what is mutation testing](https://stryker-mutator.io/docs/)).

## Decision
- Frontend: StrykerJS with the Jest runner on `src/lib`, `src/config.js` and the main components, with thresholds high 85, low 70, break 60.
- Backend: mutmut on the serving modules (retrieval, body-shape rules, artifacts, storage, image I/O, settings, shopping). mutmut does not support native Windows, so it runs in WSL locally and on Ubuntu in CI.
- Presentation-only mutants (Tailwind `className`, inline `style`) are excluded with a small Stryker ignorer plugin, and every other exclusion is an inline disable comment with a reason. Equivalent mutants are documented rather than tested.
- Mutation runs are slow, but the product owner chose to run them on every push and pull request alongside the unit tests, so nothing is skipped. They run as separate jobs so a slow mutation run does not delay the test result.

## Consequences
- Frontend score went from 63.3% to 87.8% by writing tests aimed at surviving mutants; that process also surfaced a real UX bug (the "last look" message showed too early).
- Mutation scores depend on what is excluded; the exclusions are visible in the config and source so the number can be audited.
