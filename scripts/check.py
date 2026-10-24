"""Run portable, offline checks from a fresh clone. Never use models or APIs."""
from pathlib import Path
import subprocess
import sys


def main():
    root = Path(__file__).resolve().parents[1]
    commands = [
        ["scripts/site/research_preview.py"],
        ["-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"],
        ["scripts/incidents/validate.py", "--root", "incidents/submissions"],
        ["m0/scripts/discovery/export_research.py", "--verify", "datasets/research/v0.1.0"],
        ["m0/scripts/discovery/export_research.py", "--verify", "datasets/research/v0.2.0"],
    ]
    if (root / "incidents/discovery/leads.jsonl").exists():
        commands.append(["scripts/incidents/collect.py", "--validate-cache", "incidents/discovery/leads.jsonl"])
    for command in commands:
        result = subprocess.run([sys.executable, "-I", *command], cwd=root, check=False)
        if result.returncode:
            return result.returncode
    print("Offline checks passed. No model, API key or downloaded source was used.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
