# Test 04 Normalization Guide

Test 04 has no free-form method-label normalization. The normalizer removes round
prefixes and extraction notes, adds model/provider identity, and preserves the
consolidated verdict, localization, self-correction, review-note, and evidence
fields exactly as extracted. `review_notes` is extraction metadata, not a score.

No correctness or answer-key comparison is performed in this stage.
