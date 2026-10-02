# Where these proofs come from

Written for a reader who opens this Lean folder and needs to know what was proved here and what was proved elsewhere.

The mathematics that decides this benchmark's grades was developed in the Orientation Boundary programme, not in this repository. That programme's manuscript is

> Moses Rahnama, *The Orientation Boundary for Step-Duplicating Recursors: A Machine-Checked Structural Theory of Termination Proofs*, arXiv:2512.00081.

and its public Lean formalization is the repository https://github.com/MosesRahnama/The-Orientation-Boundary.

Several modules in `KO7Benchmark/` restate, specialize or adapt results of that programme so that the scoring pipeline can cite a declaration inside this repository. `SchemaTests/`, `SANSTests/` and `ScoringAnchors/` are of that kind: they carry the barriers, the counterexamples and the successful constructions for the two kernels this benchmark uses, in the form the answer key and the scorer resolve against. The general theorems behind them, above all the closed-grammar direct-measure barrier and the declared method universe, belong to the Orientation Boundary programme.

Two consequences for anyone working here.

**Search before you formalize.** A result that looks missing is usually present in the master package in a more general form. `Meta/BoundaryGeneral/DirectMeasureGrammarClosure.lean` proves the direct-measure barrier by structural induction over a closed grammar of whole-term measures rather than family by family, and `Meta/BoundaryGeneral/DeclaredMethodUniverse.lean` carries the proof-bearing families with an explicit outside case over a 76-row method atlas.

**Cite, do not copy.** Where a general result already holds, the scoring policy cites it and this repository adds only the instance the pipeline needs. A module here that rests on the Orientation Boundary programme says so in its header.

This repository never writes to the master package.
