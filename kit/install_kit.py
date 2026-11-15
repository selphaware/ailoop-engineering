#!/usr/bin/env python
"""Install (or upgrade) the loop kit in a project.

    <project venv python> kit/install_kit.py <project_dir>

Run it WITH the project's own virtual-environment interpreter. Whichever
Python runs this script is the one pinned, by absolute path, into the hooks.
That is deliberate: the gate, the tests, the hooks and the driver must all
use the same interpreter, and it must be one YOU created.

Safe to re-run. It overwrites kit files only (hooks, driver, gatekit,
prompts, reference examples, scout agent, tests/pytest.ini), merges its hooks and deny rules into
an existing .claude/settings.json (keeping a .bak), and never touches your
gate, spec, plan, tests or application. loop/loop.json is kept if it exists,
because it holds your routing choices.

Standard library only.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent / "template"
MAPPING = {"claude": ".claude", "loop": "loop", "verify": "verify", "tests": "tests"}
KEEP_IF_PRESENT = {"loop/loop.json"}
HOOK_FILES = ("guard.py", "gate_hook.py", "stop_gate.py")
GITIGNORE = ["loop/state/", "verify/artifacts/", "__pycache__/", ".pytest_cache/",
             ".claude/settings.local.json", ".claude/settings.json.bak"]


def render_settings(python: str) -> dict:
    text = (TEMPLATE / "claude" / "settings.template.json").read_text(encoding="utf-8")
    return json.loads(text.replace("__PYTHON__", json.dumps(python)[1:-1]))


def merge_settings(existing: dict, ours: dict) -> dict:
    """Add the kit's hooks and deny rules without discarding anything else."""
    merged = dict(existing)
    perms = dict(merged.get("permissions") or {})
    deny = list(perms.get("deny") or [])
    deny += [rule for rule in ours["permissions"]["deny"] if rule not in deny]
    perms["deny"] = deny
    merged["permissions"] = perms
    hooks = dict(merged.get("hooks") or {})
    for event, groups in ours["hooks"].items():
        kept = []
        for group in hooks.get(event) or []:
            mine = any(name in " ".join(h.get("args") or []) + h.get("command", "")
                       for h in group.get("hooks") or [] for name in HOOK_FILES)
            if not mine:
                kept.append(group)
        hooks[event] = kept + groups
    merged["hooks"] = hooks
    return merged


def venv_inside(project: Path, python: str):
    """Top-level folder of ``project`` holding the interpreter's venv, or None."""
    try:
        rel = Path(python).resolve().relative_to(project.resolve())
    except (ValueError, OSError):
        return None
    top = rel.parts[0] if len(rel.parts) > 1 else None
    if top and (project / top / "pyvenv.cfg").is_file():
        return top
    return None


def install(project: Path, python: str, quiet: bool = False) -> list:
    """Copy the kit into ``project``. Returns a list of human-readable actions."""
    actions = []
    project.mkdir(parents=True, exist_ok=True)
    for src in sorted(TEMPLATE.rglob("*")):
        if src.is_dir() or "__pycache__" in src.parts or src.name == "settings.template.json":
            continue
        parts = src.relative_to(TEMPLATE).parts
        rel = Path(MAPPING[parts[0]], *parts[1:])
        dest = project / rel
        if rel.as_posix() in KEEP_IF_PRESENT and dest.exists():
            actions.append(f"kept      {rel.as_posix()} (your routing)")
            continue
        verb = "updated  " if dest.exists() else "installed"
        if dest.exists() and dest.read_bytes() == src.read_bytes():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        actions.append(f"{verb} {rel.as_posix()}")

    examples = TEMPLATE.parent / "examples"
    for src in sorted(examples.glob("*")) if examples.is_dir() else []:
        if src.is_file():                       # reference gates and plan, read-only
            dest = project / "loop" / "examples" / src.name
            if not dest.exists() or dest.read_bytes() != src.read_bytes():
                verb = "updated  " if dest.exists() else "installed"
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dest)
                actions.append(f"{verb} loop/examples/{src.name}")

    settings_path = project / ".claude" / "settings.json"
    ours = render_settings(python)
    if settings_path.exists():
        try:
            existing = json.loads(settings_path.read_text(encoding="utf-8"))
        except ValueError:
            raise SystemExit(f"{settings_path} is not valid JSON; fix or remove it, then re-run.")
        merged = merge_settings(existing, ours)
        if merged != existing:
            shutil.copyfile(settings_path, settings_path.with_suffix(".json.bak"))
            settings_path.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
            actions.append("merged    .claude/settings.json (previous copy: settings.json.bak)")
    else:
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(json.dumps(ours, indent=2) + "\n", encoding="utf-8")
        actions.append("installed .claude/settings.json")

    ignore = project / ".gitignore"
    lines = ignore.read_text(encoding="utf-8").splitlines() if ignore.exists() else []
    wanted = list(GITIGNORE)
    venv = venv_inside(project, python)
    if venv:
        wanted.append(f"/{venv}/")              # a venv kept in the repo is never committed
    missing = [g for g in wanted if g not in lines]
    if missing:
        ignore.write_text("\n".join(lines + missing) + "\n", encoding="utf-8")
        actions.append("updated   .gitignore")
    if not quiet:
        for a in actions:
            print("  " + a)
    return actions


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("project", help="project directory (a local disk, not a network path)")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    python = sys.executable

    if "windowsapps" in python.lower():
        print(f"STOP: {python} is the Microsoft Store stub, not a real interpreter.\n"
              "Run this with the project's venv python (SETUP-GUIDE.md, Part 2).")
        return 3
    if sys.version_info < (3, 10):
        print(f"STOP: Python 3.10 or newer is needed; this is {sys.version.split()[0]}.")
        return 3
    if str(project).startswith("\\\\"):
        print(f"WARNING: {project} is a network (UNC) path. Headless browsers and hooks "
              "misbehave there; use a local disk.")

    print(f"Installing the loop kit into {project}")
    print(f"Pinning interpreter: {python}")
    install(project, python)

    for module, why in (("pytest", "required: the test suite and the driver use it"),
                        ("playwright", "needed only if the gate drives a browser")):
        probe = subprocess.run([python, "-c", f"import {module}"], capture_output=True)
        if probe.returncode != 0:
            print(f"  NOTE: '{module}' is not installed in this interpreter ({why}). "
                  "Gate dependencies are yours to install, not the agent's.")

    print("\nNext:")
    print(f"  1. Put your BOOTSTRAP.md in {project}")
    print("  2. Commit (the kit is now your baseline)")
    print(f"  3. {python} loop/run_loop.py doctor")
    print(f"  4. {python} loop/run_loop.py harness")
    return 0


if __name__ == "__main__":
    sys.exit(main())
