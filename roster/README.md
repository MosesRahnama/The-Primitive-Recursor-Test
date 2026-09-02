# Central model roster

`models.json` is the **single source of truth** for the benchmark's model list. To add,
remove, or relabel a model, edit `models.json` only, then run
`python scripts/build_roster.py`. **No script code is ever touched for a roster change.**

## Flow

```
roster/models.json   (you edit this)      ordered list of model entries
        |
        |  python scripts/build_roster.py   (regenerates from models.json)
        v
roster/roster.json   (generated)          runtime roster every other script reads
roster/roster.md     (generated)          human-readable table
```

## models.json entry fields

`slug`, `display`, `provider`, `via` (direct route: anthropic, openai, openai_responses,
google, xai, zai, alibaba, minimax, deepseek, moonshot, ... or "openrouter"),
`direct_model` (the provider's native model id), `openrouter_id` (reference), `pin`
(OpenRouter upstream, usually null now), and optional `extra` (request-body fields) /
`reasoning` (toggle).

## Who reads the roster

Everything reads `roster.json` (never a hardcoded list), so a model added here appears
automatically in every run, every audit, and every report:

- `scripts/run_battery.py` - which models to run and how to route each one
- `scripts/schema_a_pipeline.py`, `scripts/schema_b_pipeline.py` - `MODEL_NAME`
- `results/normalized_data/normalize_final_extracted_data.py` - joins `model` /
  `provider` identity onto every normalized row via `session_slug`

Routing details per model (transport, source pinning, no-training policy) are in
`ROUTING.md`.

## Adding a model

Append an entry to `models.json`:

```json
{
  "slug": "new-model",
  "display": "New Model",
  "provider": "SomeProvider",
  "via": "someprovider",
  "direct_model": "new-model-native-id",
  "openrouter_id": "someprovider/new-model",
  "pin": null
}
```

Then run `python scripts/build_roster.py`. The model now shows up in the runner, the
pipelines, and the audit coverage with no code changes.
