# Coverage-oracle obligation (binding)

Policy: `tgc-coverage-oracle/1.0.0` · SHA-256 `30b2f0c904f48caba92f913ee1390699fb9e1506f6bc564cdd80ef9cfc87f00b` · merge gap `400` decoded characters.

This is a **recall check only**. It does not determine whether the text is a construction, which construction kind applies, whether the construction works, or whether it is primary. The validator locates every source region containing one or more configured signal families and requires that region to overlap an anchor used in `coverage.mention_dispositions`.

For every flagged region, do exactly one of:

1. link the anchor to one or more claims with disposition `claim`;
2. use disposition `nonconstruction` and state why the passage is only background, a catalogue, a quoted prompt, or another non-claim;
3. use disposition `unresolved` and state the source-grounded ambiguity.

Never create a claim merely to satisfy the oracle. A valid nonconstruction or unresolved disposition fully satisfies it. Validation reports the exact uncovered source range and signal labels for repair.

Configured signal families:

- `lexicographic`
- `lex order`
- `path order`
- `lpo`
- `rpo`
- `kbo`
- `knuth-bendix`
- `polynomial`
- `interpretation`
- `weight(ed)`
- `measure`
- `multiset`
- `dependency pair(s)`
- `size-change`
- `matrix`
- `exponential`
- `semantic labeling`
- `argument filtering`
- `well-founded`
- `monotone`
- `ranking function`
- `structural induction`
- `termination order`
- `subterm`
- `term size`
- `congruence`
- `context rule(s)`
- `closure rule(s)`
- `reducibility`
- `root step`
