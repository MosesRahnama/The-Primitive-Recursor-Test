import SurfaceTransport

/-!
Axiom audit for the Test 08 surface transport.
Run with `lake env lean axiom_audit.lean`; this file is not part of the library
target, so it does not alter the certified build.
-/

#print axioms SurfaceTransport.execWalkWeight
#print axioms SurfaceTransport.extractPrefix
#print axioms SurfaceTransport.execWalkWeight_nil
#print axioms SurfaceTransport.execWalkWeight_singleton
#print axioms SurfaceTransport.execWalkWeight_cons_cons
#print axioms SurfaceTransport.extractPrefix_zero
#print axioms SurfaceTransport.extractPrefix_succ
