"""Share the selected Python/Django/database combinations between local and CI."""

import argparse
import itertools
import json
import os
from pathlib import Path


def cases():
    config = json.loads((Path(__file__).resolve().parents[1] / "ci-matrix.json").read_text())
    records = []
    for python, django, database in itertools.product(
        config["python"], config["django"], config["database"]
    ):
        record = {"python": python, "django": django, "database": database}
        if record not in config["exclude"]:
            records.append({**record, "postgres_image": config["postgres_image"]})
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--github-output", action="store_true")
    args = parser.parse_args()
    value = json.dumps({"include": cases()}, separators=(",", ":"))
    if args.github_output:
        with Path(os.environ["GITHUB_OUTPUT"]).open("a") as output:
            output.write(f"matrix={value}\n")
    print(value)


if __name__ == "__main__":
    main()
