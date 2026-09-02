/-
  Full one-hole context closure of the eight KO7 root rules.

  `KO7Kernel.Step` is deliberately root-only.  This relation makes the
  stronger contextual target explicit so evidence for root termination,
  dependency-pair termination, and full TRS termination cannot be conflated.
-/
import KO7Benchmark.KO7Kernel

namespace KO7Benchmark.KO7ContextClosure

open KO7Benchmark.KO7Kernel
open Trace

inductive StepCtx : Trace → Trace → Prop
  | root {t u : Trace} : Step t u → StepCtx t u
  | delta {t u : Trace} : StepCtx t u → StepCtx (delta t) (delta u)
  | integrate {t u : Trace} : StepCtx t u → StepCtx (integrate t) (integrate u)
  | mergeLeft {t t' u : Trace} : StepCtx t t' → StepCtx (merge t u) (merge t' u)
  | mergeRight {t u u' : Trace} : StepCtx u u' → StepCtx (merge t u) (merge t u')
  | appLeft {f f' t : Trace} : StepCtx f f' → StepCtx (app f t) (app f' t)
  | appRight {f t t' : Trace} : StepCtx t t' → StepCtx (app f t) (app f t')
  | recBase {b b' s n : Trace} :
      StepCtx b b' → StepCtx (recDelta b s n) (recDelta b' s n)
  | recStep {b s s' n : Trace} :
      StepCtx s s' → StepCtx (recDelta b s n) (recDelta b s' n)
  | recCounter {b s n n' : Trace} :
      StepCtx n n' → StepCtx (recDelta b s n) (recDelta b s n')
  | eqLeft {a a' b : Trace} : StepCtx a a' → StepCtx (eqW a b) (eqW a' b)
  | eqRight {a b b' : Trace} : StepCtx b b' → StepCtx (eqW a b) (eqW a b')

def StepCtxRev : Trace → Trace → Prop := fun t u => StepCtx u t

end KO7Benchmark.KO7ContextClosure
