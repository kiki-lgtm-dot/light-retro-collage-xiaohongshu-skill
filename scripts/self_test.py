#!/usr/bin/env python3
"""Render and validate the bundled six-page example in a temporary directory."""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path


def run(command: list[str]) -> None:
    print("+", " ".join(command))
    subprocess.run(command, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", help="Optional CJK font path")
    parser.add_argument("--keep-output", type=Path, help="Write output here instead of a temporary directory")
    args = parser.parse_args()
    skill = Path(__file__).resolve().parents[1]
    project = skill / "assets" / "examples" / "agent-skill-demo.json"
    temporary = None
    try:
        if args.keep_output:
            output = args.keep_output.resolve()
            output.mkdir(parents=True, exist_ok=True)
        else:
            temporary = tempfile.TemporaryDirectory(prefix="retro-collage-xhs-self-test-")
            output = Path(temporary.name)
    except (OSError, RuntimeError):
        print("SELF TEST FAILED: output directory could not be prepared", file=sys.stderr)
        return 2
    render = [sys.executable, str(skill / "scripts" / "render_note.py"), str(project), "--output", str(output)]
    if args.font is not None:
        render.extend(["--font", args.font])
    try:
        run(render)
        run([sys.executable, str(skill / "scripts" / "validate_note.py"), str(project), "--output", str(output)])
        run([sys.executable, str(skill / "scripts" / "make_contact_sheet.py"), str(output / "pages"), "--output", str(output / "qa" / "contact-sheet.png")])
    except subprocess.CalledProcessError as exc:
        command_name = Path(exc.cmd[1]).name if len(exc.cmd) > 1 else "child command"
        print(f"SELF TEST FAILED: {command_name} exited with status {exc.returncode}", file=sys.stderr)
        return 3
    finally:
        if temporary is not None:
            temporary.cleanup()
    if temporary is None:
        print(f"SELF TEST PASSED: {output}")
    else:
        print("SELF TEST PASSED: temporary output validated and removed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
