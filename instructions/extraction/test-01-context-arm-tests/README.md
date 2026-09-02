# Test 01 (KO7 kernel) Extraction Prompts

Round-by-round extractor instructions for this surface: `TEST01_CONTEXT_ROUND1_PROMPTS.md`, `TEST01_CONTEXT_ROUND2_PROMPTS.md`, `TEST01_CONTEXT_ROUND3_PROMPTS.md`, `TEST01_CONTEXT_ROUND4_PROMPTS.md` (construction transcription; dual-pass, gated, transcribe-only).

One extractor per round, one output file. The round-N extractor reads only the response file allowed for that round and fills only the still-blank round-N cells of `results\test-01-context-arm-tests\extraction\TEST01_CONTEXT_r{N}.csv`, keeping the ledger row order. No second extractor and no consolidator role.
