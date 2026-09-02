# Test 03 (completion, ordinal) Extraction Prompts

Round-by-round extractor instructions for this surface: `TEST03_ROUND1_PROMPTS.md`, `TEST03_ROUND2_PROMPTS.md`, `TEST03_ROUND3_PROMPTS.md` (obligation-stance transcription; dual-pass, gated, transcribe-only).

One extractor per round, one output file. The round-N extractor reads only the response file allowed for that round and fills only the still-blank round-N cells of `results\test-03-completion-tests-ordinal\extraction\TEST03_r{N}.csv`, keeping the ledger row order. No second extractor and no consolidator role.
