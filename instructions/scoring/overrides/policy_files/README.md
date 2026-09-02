# Scoring Policy Mirrors

These files are read-only mirrors of the canonical policies under `scoring\`. They define construction-level method scoring, surface-specific rules, and corrected Test 03 semantics. The live canonical file governs whenever a mirror differs; refresh the mirror by copying the canonical file.

The active contract is one auditor per override surface: a single agent reads every raw response for its surface and writes only its override CSV under `results\final_scored_data\overrides\`. There are no parallel reviewers and no adjudication step.
