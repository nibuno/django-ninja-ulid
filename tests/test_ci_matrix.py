"""Check the full compatibility matrix and the combinations used on pull requests."""

import importlib.util
import json
import sys
from itertools import product
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ci_matrix", ROOT / "scripts/ci_matrix.py")
ci_matrix = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci_matrix)
CONFIG = json.loads((ROOT / "ci-matrix.json").read_text())


def test_full_matrix_covers_all_supported_combinations():
    full = ci_matrix.cases()
    assert len(full) == 12
    assert full == [
        {
            "python": python,
            "django": django,
            "database": database,
            "postgres_image": CONFIG["postgres_image"],
        }
        for python, django, database in product(
            CONFIG["python"], CONFIG["django"], CONFIG["database"]
        )
    ]


def test_pr_subset_covers_oldest_and_newest_pairs_on_both_databases():
    full = ci_matrix.cases()
    subset = ci_matrix.cases("pr")
    pairs = {
        (CONFIG["python"][0], CONFIG["django"][0]),
        (CONFIG["python"][-1], CONFIG["django"][-1]),
    }
    assert len(subset) == 4
    assert subset == [case for case in full if (case["python"], case["django"]) in pairs]


def test_github_output_uses_requested_subset(tmp_path, monkeypatch, capsys):
    output = tmp_path / "github-output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setattr(sys, "argv", ["ci_matrix.py", "--github-output", "--subset", "pr"])

    ci_matrix.main()

    value = capsys.readouterr().out
    assert json.loads(value) == {"include": ci_matrix.cases("pr")}
    assert output.read_text() == f"matrix={value}"
