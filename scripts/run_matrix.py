"""Run the CI combinations locally against non-editable wheel installations.

PostgreSQL must already be available through ULID_POSTGRES_* variables. This
script does not start, stop, or reuse any existing application database server.
"""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import tomllib
import xml.etree.ElementTree as ET

from ci_matrix import cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uv", default=shutil.which("uv"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    destination = root / "local-checks/matrix"
    destination.mkdir(parents=True, exist_ok=True)
    wheel = next((root / "dist").glob("*.whl"))
    records = []
    prepared = {}
    locked = tomllib.loads((root / "uv.lock").read_text())
    driver_version = next(item["version"] for item in locked["package"] if item["name"] == "psycopg")

    for case in cases():
        key = f"py{case['python']}-django{case['django']}"
        label = f"{key}-{case['database']}"
        folder = destination / label
        folder.mkdir(exist_ok=True)
        environment = os.environ.copy()
        environment.pop("PYTHONPATH", None)
        environment["ULID_TEST_DATABASE"] = case["database"]
        record = {**case, "status": "running", "log": str(folder / "run.log")}
        started = time.monotonic()

        def run(command):
            result = subprocess.run(command, cwd=root, env=environment, text=True, capture_output=True)
            with (folder / "run.log").open("a") as log:
                log.write(result.stdout + result.stderr)
            if result.returncode:
                raise RuntimeError(f"Command failed ({result.returncode}): {command[0]} {command[1]}\n{result.stdout[-3000:]}\n{result.stderr[-3000:]}")
            return result.stdout

        try:
            if key not in prepared:
                interpreter = shutil.which(f"python{case['python']}")
                if not interpreter:
                    raise RuntimeError(f"Python {case['python']} is not installed")
                env_path = destination / "environments" / key
                if not (env_path / "bin/python").exists():
                    run([args.uv, "venv", "--python", interpreter, str(env_path)])
                python = str(env_path / "bin/python")
                run([args.uv, "pip", "install", "--reinstall-package", "django-ninja-ulid", "--default-index", "https://pypi.org/simple", "--python", python,
                     str(wheel) + "[orm]", f"Django=={case['django']}",
                     "pytest==9.1.1", "pytest-django==4.14.0", f"psycopg[binary]=={driver_version}"])
                run([args.uv, "pip", "check", "--python", python])
                prepared[key] = python
                if case["database"] == "sqlite":
                    base_path = destination / "base-environments" / key
                    if not (base_path / "bin/python").exists():
                        run([args.uv, "venv", "--python", interpreter, str(base_path)])
                    base_python = str(base_path / "bin/python")
                    run([args.uv, "pip", "install", "--reinstall-package", "django-ninja-ulid", "--default-index", "https://pypi.org/simple", "--python", base_python,
                         str(wheel), f"Django=={case['django']}"])
                    run([base_python, "-I", str(root / "scripts/check_type_install.py"), "--output", str(folder / "base-install.json")])

            python = prepared[key]
            versions = run([python, "-I", "-c", 'import importlib.metadata,json,sys; print(json.dumps({"python":sys.version.split()[0],"versions":{name:importlib.metadata.version(name) for name in ["Django","django-ninja","pydantic","python-ulid","python-ulid-django","psycopg"]}}))'])
            runtime = json.loads(versions)
            record["python_full"] = runtime["python"]
            record["versions"] = runtime["versions"]
            run([python, "-m", "pytest", str(root / "tests"), "-q", f"--junitxml={folder / 'pytest.xml'}"])
            suites = list(ET.parse(folder / "pytest.xml").getroot().iter("testsuite"))
            record["tests"] = sum(int(s.get("tests", 0)) for s in suites)
            run([python, str(root / "scripts/check_install.py"), "--output", str(folder / "fresh-project.json")])
            record["fresh_project"] = json.loads((folder / "fresh-project.json").read_text())
            record["status"] = "passed"
        except Exception as error:
            record["status"] = "failed"
            record["error"] = str(error)
        record["elapsed_seconds"] = round(time.monotonic() - started, 2)
        records.append(record)
        (destination / "results.json").write_text(json.dumps({"cases": records}, indent=2) + "\n")
        print(json.dumps({"case": label, "status": record["status"], "tests": record.get("tests"), "error": record.get("error")}), flush=True)

    if any(record["status"] != "passed" for record in records):
        sys.exit(1)


if __name__ == "__main__":
    main()
