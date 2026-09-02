# Schema A New System (SANS) Extraction Prompts

Round-by-round extractor instructions for this surface: `SCHEMA_A_NEW_SYSTEM_ROUND1_PROMPTS.md`, `SCHEMA_A_NEW_SYSTEM_ROUND2_PROMPTS.md`, `SCHEMA_A_NEW_SYSTEM_ROUND3_PROMPTS.md`, `SCHEMA_A_NEW_SYSTEM_ROUND4_PROMPTS.md`, `SCHEMA_A_NEW_SYSTEM_ROUND5_PROMPTS.md` (construction transcription; dual-pass, gated, transcribe-only).

One extractor per round, one output file. The round-N extractor reads only the response file allowed for that round and fills only the still-blank round-N cells of `results\schema-test-A-new-system-tests\extraction\SCHEMA_A_NEW_SYSTEM_r{N}.csv`, keeping the ledger row order. No second extractor and no consolidator role.
