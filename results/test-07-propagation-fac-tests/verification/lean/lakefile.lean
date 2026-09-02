import Lake

open Lake DSL

package Test07Verification where

@[default_target]
lean_lib Test07Verification where
  srcDir := "../../../../lean"
  roots := #[`Test07Verification]
