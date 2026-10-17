# DLBCL Harbor Sample Runs

These runs use each task's local verifier entrypoint, `tests/test.sh`.

The verifier is only a development smoke test. A production Harbor evaluator should use the official harness and physician-reviewed rubric interpretation.

## Narrative Case

Command:

```bash
harbor_cases/dlbcl_0001_narrative/tests/test.sh
```

Result:

- Reward: 1.0
- Raw score: 100 / 100
- Penalty: 0
- Final score: 100 / 100
- Passed: true
- Critical errors: none
- Output file: `harbor_cases/dlbcl_0001_narrative/results/reward.json`

Equivalent Harbor sanity-check flow once Harbor is installed:

```bash
harbor run -p ./harbor_cases/dlbcl_0001_narrative -a oracle
```

## FHIR Case

Command:

```bash
harbor_cases/dlbcl_0001_fhir/tests/test.sh
```

Result:

- Reward: 1.0
- Raw score: 100 / 100
- Penalty: 0
- Final score: 100 / 100
- Passed: true
- Critical errors: none
- Output file: `harbor_cases/dlbcl_0001_fhir/results/reward.json`

Equivalent Harbor sanity-check flow once Harbor is installed:

```bash
harbor run -p ./harbor_cases/dlbcl_0001_fhir -a oracle
```

## What Was Scored

Both sample responses correctly identified:

- DLBCL, NOS
- Non-GCB phenotype by Hans algorithm
- Lugano/Ann Arbor stage III bulky disease
- Double-expressor lymphoma, not double-hit lymphoma
- IPI and CNS-IPI as required prognostic tools
- Pola-R-CHP as an appropriate contemporary first-line option
- R-CHOP as an acceptable alternative
- No automatic CNS prophylaxis from supplied data alone
- PET-CT response assessment using Lugano/Deauville criteria
