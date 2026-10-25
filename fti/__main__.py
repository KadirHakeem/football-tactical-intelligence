"""Run the full Phase 1 pipeline in order with one command.

From the project root:
    python -m fti                 # all steps (first run downloads ~1.2 GB of match data)
    python -m fti --skip-ingest   # reuse the existing local cache

Steps: ingest -> substitutions -> first_sub -> robustness -> charts.
Stops at the first failing step.
"""
from __future__ import annotations

import argparse
import time

from fti import charts, first_sub, ingest, robustness, substitutions


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full analysis pipeline.")
    parser.add_argument("--skip-ingest", action="store_true", help="use the existing data cache")
    args = parser.parse_args()

    steps = [
        ("substitutions: score at every substitution", substitutions.main),
        ("first_sub: timing by score state + sensitivity", first_sub.main),
        ("robustness: margin split + permutation tests", robustness.main),
        ("charts: figures", charts.main),
    ]
    if not args.skip_ingest:
        steps.insert(0, ("ingest: download/cache match data", lambda: ingest.main([])))

    start = time.perf_counter()
    for i, (name, step) in enumerate(steps, start=1):
        print(f"\n=== [{i}/{len(steps)}] {name} ===")
        t0 = time.perf_counter()
        step()
        print(f"--- done in {time.perf_counter() - t0:.1f}s")
    print(f"\nPipeline complete in {time.perf_counter() - start:.1f}s. Results in results/.")


if __name__ == "__main__":
    main()
