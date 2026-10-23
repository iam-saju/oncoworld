# Cross-step carry-forward in multi-step Harbor tasks

How much context an L2/L3 step of a multi-step task (e.g. `intracranial_mesenchymal_journey_v1`) actually
has about earlier steps - investigated directly against Harbor 0.24.0's source and a real saved trial,
2026-10-23/24, while scoping cross-step dependency rubric items for the mesenchymal journey case.

## The agent's conversation is fresh every step, by design

`harbor/trial/multi_step.py`'s `MultiStepTrial._step_resumes`:

```python
def _step_resumes(self, index: int) -> bool:
    return self.config.agent.resume_trajectory and index > 1
```

`resume_trajectory` defaults to `False` (`harbor/models/trial/config.py:102`) and is not set in any
`configs/harbor-*-mesenchymal-journey-fhir.json`. Without it, `_reset_agent_logs_for_step` wipes the agent's
session directory before every step but the first:

```python
async def _reset_agent_logs_for_step(self, *, resume: bool) -> None:
    if self.agent_environment.capabilities.mounted:
        return
    if resume:
        return
    await self.agent_environment.empty_dirs([self.agent_env_paths.agent_dir], chmod=True)
```

Confirmed empirically in a real run (`jobs/haiku_mesenchymal_journey/2026-10-23__18-18-52/...`): the saved
`trajectory.json` for L1, L2, and L3 each carry a different `session_id` (`d7bcabec...`, `fd922709...`,
`5fe898dc...`). Each step is a cold-start agent invocation with no native memory of earlier steps.

## Instructions are never written to a container file

`harbor/trial/trial.py`'s `_run_agent_phase` takes `instruction: str` and passes it straight into
`running_agent.run(...)` (or `.resume`/`.load`) - a plain Python string, held in memory for that one
invocation only, never written to disk inside the container. The real trial log for the same run confirms
this independently: the agent is launched via

```
opencode --model=opencode-go/<model> run --format=json --thinking --dangerously-skip-permissions -- '<full
instruction text, verbatim>'
```

- the instruction text embedded directly in the CLI invocation, not read from a file Harbor uploaded. There
is no `setup.sh` in any mesenchymal-journey step, and `_upload_step_workdir` only uploads each step's
declared `workdir/` directory (case/FHIR files) - never `instruction.md` itself.

## But the container's filesystem persists across steps

`MultiStepTrial._run()` calls `_stop_agent_environment()` exactly once, after the whole step loop - not
between steps. Each step's workdir is uploaded *additively* (`_upload_step_workdir` -> `upload_dir`, never a
delete). So anything written to disk by an earlier step - case files, and critically **the model's own prior
answer JSON files** under `/app/answers/` - physically persists and is readable by a later step's agent, if
it chooses to look.

## What this means for a specific fact: the L2 biopsy refusal

The mesenchymal journey's L2 step (`steps/L2-molecular-access/instruction.md`, q3) states: "The family is
not willing for a repeat brain biopsy." Checked precisely where this fact lives, since it determines whether
an L3 rubric item testing for it is fair:

- **Not in any chart/FHIR file.** Decoded L2's actual `fhir_updates/01_2026-12-15_update.json`
  DocumentReference (the interval-history note) directly - it documents the resection, surgical pathology,
  STAT6-negative IHC, postoperative RT, and surveillance MRI. No mention of a biopsy refusal anywhere in it.
- **Not restated in L3's instruction.md.** L3's prompt only says "Your earlier answers are in
  `/app/answers/`" - it does not repeat the refusal sentence.
- **So the only path is the model's own L2 answer file**, `/app/answers/L2_molecular_access.json`, which
  does persist into L3 (confirmed above) and which L3's instruction.md explicitly points at.

Checked whether that path is actually exercised, across all 4 real L2 answers on file at the time of this
investigation (native Claude-Code Haiku, OpenCode-Haiku-go, Qwen3.7-Plus, GPT-6-Luna): every one of them
restates the refusal in its own words when answering q3 -

- Haiku (native): "I would not proceed with a repeat brain biopsy against the patient's wishes."
- OpenCode-Haiku-go: "respect the family's refusal of repeat brain biopsy"
- Qwen3.7-Plus: "With the family declining a repeat brain biopsy"
- GPT-6-Luna: "If the family declines another brain biopsy"

This isn't coincidence - q3's own prompt presents the refusal as the premise the model must respond to, so
any coherent answer ends up restating it, in the one file that actually persists to the next step.

Also checked whether a fresh L3 agent actually *uses* this path in practice, not just whether it could: the
real Haiku L3 trajectory shows the agent running `ls -la /app/case /app/case/fhir_updates /app/answers; wc -c
... /app/answers/*` - it noticed its own prior answer files exist and checked their size, but never `cat`
their content. So in that trial, Haiku almost certainly did not recover the specific refusal, even though it
was sitting right there.

## Conclusion

A rubric item testing whether L3 honors the L2 biopsy refusal is a fair test of genuine cross-step carry-
forward - but only through the "the model's own prior answer file" path, since there is no chart fact to
fall back on and L3's prompt does not restate it. Two things follow directly:

1. A fail-closed calibration test must simulate an L3 agent that never read `/app/answers/L2_molecular_access.json`
   - using only facts L3's own instruction.md restates.
2. The paired `should` item's rule must require refusal-specific language (declin*/refus*/not willing/
   against ... wishes, tied to family/patient + biopsy) - not something inferable from L3's own restated
   "liquid biopsy pending" fact alone (e.g. "given limited tissue, rely on the liquid biopsy" must not
   satisfy it; that's generic tissue-scarcity reasoning, not evidence the refusal was carried forward).

This generalizes beyond this one item: any future cross-step dependency item in this or another multi-step
case must be checked against the same two facts - is the carried-forward information written to a file that
survives into the later step, and is that file one the later step's agent is actually told to look at - or
it risks silently testing reading comprehension of the current step's own prompt instead.
