"""Shared fixtures: a throwaway project with the kit installed by the real installer."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT))
sys.path.insert(0, str(KIT / "template" / "loop"))
import install_kit  # noqa: E402

CSV = "deal_id,stage,value_gbp\n1,Proposal,100\n2,Negotiation,300\n3,Closed Won,50\n"

STUB = '''
def load(path):
    raise NotImplementedError
def total(rows):
    raise NotImplementedError
def weighted_total(rows):
    raise NotImplementedError
'''
_HEAD = '''
import csv
PROB = {"Proposal": 0.5, "Negotiation": 0.75, "Closed Won": 1.0}
def load(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return [dict(r, value_gbp=float(r["value_gbp"])) for r in csv.DictReader(fh)]
'''
LOADER = _HEAD + '''
def total(rows):
    raise NotImplementedError
def weighted_total(rows):
    raise NotImplementedError
'''
GOOD = _HEAD + '''
def total(rows):
    return sum(r["value_gbp"] for r in rows)
def weighted_total(rows):
    return sum(r["value_gbp"] * PROB[r["stage"]] for r in rows)
'''
EMPTY_LOADER = LOADER.replace(
    'return [dict(r, value_gbp=float(r["value_gbp"])) for r in csv.DictReader(fh)]', "return []")
DEAD_LOOKUP = GOOD.replace('PROB[r["stage"]]', 'PROB.get(r["stage"] + "?", 1.0)')

TESTS = {
    "tests/test_skeleton.py": '''
def test_report_exposes_api():
    from app import report
    for name in ("load", "total", "weighted_total"):
        assert callable(getattr(report, name))
''',
    "tests/test_load.py": '''
import csv
from pathlib import Path
DATA = Path(__file__).resolve().parents[1] / "data" / "deals.csv"

def test_f1_loader_returns_every_row():
    """F1: the loader must not drop rows."""
    from app import report
    with DATA.open(newline="") as fh:
        want = len(list(csv.DictReader(fh)))
    assert len(report.load(DATA)) == want
''',
    "tests/test_totals.py": '''
import csv
from pathlib import Path
DATA = Path(__file__).resolve().parents[1] / "data" / "deals.csv"

def test_total_reconciles_with_source():
    from app import report
    with DATA.open(newline="") as fh:
        want = sum(float(r["value_gbp"]) for r in csv.DictReader(fh))
    assert abs(report.total(report.load(DATA)) - want) < 0.005

def test_f2_weighted_is_below_total():
    """F2: the probability lookup must really be applied."""
    from app import report
    rows = report.load(DATA)
    assert 0 < report.weighted_total(rows) < report.total(rows)
''',
}

HAPPY = {
    "build:T1:haiku": [{"write": {"app/__init__.py": "", "app/report.py": STUB,
                                  "requirements.txt": ""}}],
    "build:T2:sonnet": [{"write": {"app/report.py": LOADER}}],
    "build:T3:opus": [{"write": {"app/report.py": GOOD}}],
    "review:*:*": [{"result": "VERDICT: SHIP\n\nNo findings."}],
}


class Project:
    def __init__(self, root: Path):
        self.root = root
        self.log = root.parent / "fake.log"
        self.scenario = root.parent / "scenario.json"

    def write(self, rel, text):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def read(self, rel):
        return (self.root / rel).read_text(encoding="utf-8")

    def env(self, **extra):
        env = dict(os.environ)
        for name in ("LOOP_STAGE", "LOOP_ACCEPT", "LOOP_TASK", "LOOP_DRIVER", "CLAUDE_PROJECT_DIR"):
            env.pop(name, None)
        env.update({
            "LOOP_CLAUDE_CMD": json.dumps([sys.executable, str(Path(__file__).parent / "fake_claude.py")]),
            "FAKE_SCENARIO": str(self.scenario), "FAKE_LOG": str(self.log),
        })
        env.update(extra)
        return env

    def drive(self, *args, scenario=None, **env):
        if scenario is not None:
            self.scenario.write_text(json.dumps(scenario), encoding="utf-8")
            self.scenario.with_suffix(".count").unlink(missing_ok=True)
        return subprocess.run([sys.executable, str(self.root / "loop" / "run_loop.py"), *args],
                              cwd=self.root, env=self.env(**env), capture_output=True, text=True)

    def calls(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]

    def state(self):
        return json.loads(self.read("loop/state/state.json"))

    def hook(self, name, payload, **env):
        """Run a hook exactly as Claude Code does: JSON on stdin, exit code out."""
        return subprocess.run([sys.executable, str(self.root / ".claude" / "hooks" / name)],
                              input=json.dumps(payload), cwd=self.root, capture_output=True,
                              text=True, env=self.env(CLAUDE_PROJECT_DIR=str(self.root), **env))

    def gate(self, *args):
        return subprocess.run([sys.executable, "verify/smoke_test.py", *args], cwd=self.root,
                              capture_output=True, text=True, env=self.env())


def make_project(tmp_path, with_tests=True) -> Project:
    root = tmp_path / "proj"
    install_kit.install(root, sys.executable, quiet=True)
    proj = Project(root)
    shutil.copyfile(KIT / "examples" / "smoke_test.example.py", root / "verify" / "smoke_test.py")
    proj.write("plan/tasks.json", (KIT / "examples" / "tasks.example.json").read_text(encoding="utf-8"))
    proj.write("data/deals.csv", CSV)
    proj.write("spec.md", "# Spec\n")
    proj.write("CLAUDE.md", "# Conventions\n")
    proj.write("BOOTSTRAP.md", "# Brief\n")
    if with_tests:
        for rel, text in TESTS.items():
            proj.write(rel, text)
    return proj


@pytest.fixture
def project(tmp_path):
    return make_project(tmp_path)


@pytest.fixture
def bare_project(tmp_path):
    """Kit, gate and plan in place, but no test suite yet."""
    return make_project(tmp_path, with_tests=False)


ML_PLAN = {
    "version": 1, "deliverable": "app",
    "tasks": [{
        "id": "T1", "title": "Profiler", "tier": "complex", "depends_on": [],
        "writes": ["app/profiler.py"], "brief": "Implement profile() per spec.md.",
        "gate_checks": ["rows.reconcile", "signal.detected", "leak.flagged", "noise.no_signal"],
        "tests": [],
    }],
}


def ml_sources():
    """GOOD and BROKEN profiler sources from the ML example gate."""
    import importlib.util
    sys.path.insert(0, str(KIT / "template" / "verify"))
    spec = importlib.util.spec_from_file_location(
        "ml_example_gate", KIT / "examples" / "smoke_test.ml.example.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.GOOD, module.BROKEN


@pytest.fixture
def ml_project(tmp_path):
    """Kit plus the ML example gate: one slow check, score bands, seeded data."""
    root = tmp_path / "proj"
    install_kit.install(root, sys.executable, quiet=True)
    proj = Project(root)
    shutil.copyfile(KIT / "examples" / "smoke_test.ml.example.py", root / "verify" / "smoke_test.py")
    proj.write("plan/tasks.json", json.dumps(ML_PLAN))
    for name in ("spec.md", "CLAUDE.md", "BOOTSTRAP.md"):
        proj.write(name, "# x\n")
    return proj
