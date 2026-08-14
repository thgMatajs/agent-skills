#!/usr/bin/env python3
"""Tier 3 paired-eval harness: does a skill actually change behavior?

There is no model API inside this script, so it orchestrates the paired eval and
does the math — it does NOT invent scores. Flow:

  1. `prompts`  — emit the with_skill / without_skill dispatch prompts for each
                  dataset task. You (the parent agent) dispatch these as subagents,
                  run >=3 reps per arm, and have a judge grade each output against
                  the task's expected_behavior bullets (pass fraction 0..1).
  2. record     — put the judge scores + token/time cost into a results.json.
  3. `score`    — compute Pass-Rate Gain (PRG) and Efficiency-Cost Gain (ECG).

PRG = mean(pass_with) - mean(pass_without).  Positive = the skill earns its context.
ECG = clip(token_saving, -1, 1)/2 + clip(time_saving, -1, 1)/2, where a *saving* is
      (without - with)/without. Negative ECG = the skill costs more than it returns.

Usage:
  python paired_eval.py prompts dataset.json
  python paired_eval.py score results.json
"""
import json
import sys


def clip(x, lo=-1.0, hi=1.0):
    return max(lo, min(hi, x))


def cmd_prompts(dataset_path):
    data = json.load(open(dataset_path))
    skill = data["skill_path"]
    for i, t in enumerate(data["tasks"], 1):
        crit = "\n".join(f"     - {b}" for b in t["expected_behavior"])
        print(f"\n===== TASK {i}: {t['query']!r} =====")
        print(f"[without_skill] (baseline — do NOT load the skill)\n"
              f"  {t['query']}\n  Files: {t.get('files', [])}")
        print(f"[with_skill]\n"
              f"  First read and follow {skill}. Then: {t['query']}\n"
              f"  Files: {t.get('files', [])}")
        print(f"  Judge both arms against expected_behavior (pass fraction 0..1):\n{crit}")
    print("\nRun >=3 reps per arm. Record pass fractions + tokens + duration_ms "
          "into results.json, then: python paired_eval.py score results.json")


def cmd_score(results_path):
    r = json.load(open(results_path))
    w, wo = r["with_skill"], r["without_skill"]

    def mean(xs):
        return sum(xs) / len(xs) if xs else 0.0

    prg = mean(w["pass"]) - mean(wo["pass"])
    tok_saving = (mean(wo["tokens"]) - mean(w["tokens"])) / max(mean(wo["tokens"]), 1)
    time_saving = (mean(wo["duration_ms"]) - mean(w["duration_ms"])) / max(mean(wo["duration_ms"]), 1)
    ecg = clip(tok_saving) / 2 + clip(time_saving) / 2

    print(f"Skill: {r.get('skill', '?')}   reps: with={len(w['pass'])} without={len(wo['pass'])}")
    print(f"  pass:   with={mean(w['pass']):.2f}  without={mean(wo['pass']):.2f}")
    print(f"  PRG   = {prg:+.2f}   ({'earns its context' if prg > 0 else 'NO gain — flag it'})")
    print(f"  tokens: with={mean(w['tokens']):.0f}  without={mean(wo['tokens']):.0f}")
    print(f"  ECG   = {ecg:+.2f}   (token_saving={tok_saving:+.2f}, time_saving={time_saving:+.2f})")
    # Variance check — writing-skills: converging reps = binding guidance.
    spread = max(w["pass"]) - min(w["pass"]) if w["pass"] else 0
    if spread > 0.34:
        print(f"  WARN: with_skill pass spread {spread:.2f} across reps — wording may not bind.")
    if prg <= 0:
        sys.exit(1)


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ("prompts", "score"):
        print(__doc__)
        sys.exit(2)
    (cmd_prompts if sys.argv[1] == "prompts" else cmd_score)(sys.argv[2])


if __name__ == "__main__":
    main()
