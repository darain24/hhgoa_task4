# Verification report

- All 20 organizer benchmark cases produced validated drafts.
- All 20 cases completed local Ollama evidence review.
- Latest case totals: 9,740 measured tokens, 603.84 summed investigation/review seconds. Cached reruns consume zero model tokens.
- 33 backend tests pass; production frontend build passes; Ruff lint passes.
- Local all-minilm embedding dimensionality verified: 384.
- UI inspected in the in-app browser, including the graph and scenario dialog.
- TigerGraph verified cases: 0/20. No workspace is configured.
- No paid API or billing was activated.

## Investigation quality

The deterministic investigation diagnostic on a selected 40-case October sample is weak and heavily abstains. It must not be marketed as accurate because its JSON is valid. A separately trained historical statistical model performs better on the October development cohort but shows a distribution mismatch on the benchmark; it stays advisory. Improving and reviewing verdicts is a remaining submission requirement.

## Remote and publication gates

TigerGraph schema compilation, graph and vector retrieval, case persistence, final answer promotion, a recorded demo, and publication remain unverified or pending. The app intentionally exposes these limitations and blocks final exports.
