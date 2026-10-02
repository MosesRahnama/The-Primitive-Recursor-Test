# TGC v3 examples — Schema Test A

These are binding calibration patterns. Each source span is exact; the JSON is the exact classification excerpt required for that pattern. Add the ordinary source anchors, axis evidence, roles, targets, primary attribution, and coverage required by the record template.

## 1. Bare recursive-call descent states no quantity (`bare_recursive_call_descent_omits_measure`)

Exact source span 1:

```text
The third argument of the recursive call strictly decreases.
```

Binding classification excerpt:

```json
{
  "claims": [
    {
      "kind": "call_measure",
      "specificity": "concrete",
      "transcription": {
        "scope": "dependency_pair",
        "argument": 3
      }
    }
  ],
  "handling": "Do not add measure=size, depth, or S_count when the response names no quantity."
}
```
