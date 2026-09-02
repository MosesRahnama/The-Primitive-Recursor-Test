# Roster routing (how each model is reached)

Every model in `models.json` / `roster.json` carries two routing fields. The runner
(`scripts/run_battery.py`, driven by `scripts/corpus_run.py`) reads them; there is
**one engine and one code path for every model** — routing is data, not a per-model
script.

| field | meaning |
|---|---|
| `via` | which transport: a direct native provider API, or `openrouter` |
| `pin` | the no-training upstream provider to source-pin to (sent as `provider.order=[pin]`, with `data_collection: "deny"`) |

`via` values:

- `anthropic`, `openai`, `openai_responses`, `google`, `xai`, `zai`, `alibaba`,
  `minimax`, `deepseek`, `moonshot` — a **direct** call to that provider's native
  API using the verified endpoint, auth, and no-training data policy for that provider.
- `openrouter` — routed through OpenRouter, source-pinned to `pin` with
  `data_collection: "deny"` and `transforms: []` (kept as close to a direct call as
  possible; no middle-out rewriting, no training).

## GLM (glm-5, glm-5.2): `via = openrouter`, `pin = z-ai`

GLM is the one model family deliberately routed through OpenRouter rather than the
direct Z.AI API, decided 2026-06-28.

- **Why:** the direct Z.AI API (`api.z.ai`) intermittently *wedges* on the heavy
  Test-01 / Schema prompts — it accepts the request and then returns no bytes for
  ~460s (a read timeout), even though a trivial call returns in ~3s and glm-5.2
  genuinely needs ~250s (it emits a ~53k-char reasoning trace). This made direct GLM
  runs unreliable and slow to complete.
- **Fix:** OpenRouter, **pinned to z-ai**, delivers the same model on the same heavy
  prompt reliably. Verified 2026-06-28: `z-ai/glm-5.2` via OpenRouter pinned z-ai
  returned in ~140s (served-by Z.AI), where the direct call was wedging. OpenRouter's
  connection handling gets through where the raw socket does not.
- **No-training preserved:** the pin (`z-ai`) plus `data_collection: "deny"` keeps
  the request on the no-training Z.AI source upstream, identical guarantee to the
  direct call. The served provider is recorded in each `session.json` (`provider`).
- **Same engine:** this is only a `via` change. GLM runs through the identical
  `run_battery.py` path and the identical per-test launchers as every other model;
  it is simply first in the roster (slow-first ordering) and reached over OpenRouter.

To reproduce a run, launch any per-test script, e.g. `python scripts/runners/run_test-01-fruit.py`;
GLM's route is taken from the roster automatically and stamped into every session.
