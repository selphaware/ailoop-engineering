"""The gate framework: exit codes, output contract, and the self-test."""
import json


def last_json(text):
    return json.loads([l for l in text.splitlines() if l.startswith("{")][-1])


def test_selftest_proves_the_example_gate_discriminates(project):
    run = project.gate("--selftest")
    assert run.returncode == 0, run.stdout + run.stderr
    assert "SELFTEST: PASS" in run.stdout
    assert "F1 caught by" in run.stdout and "F2 caught by" in run.stdout
    assert not (project.root / "verify/artifacts/_selftest").exists()  # cleans up


def test_list_and_matrix(project):
    listed = last_json(project.gate("--list", "--json").stdout)
    assert [c["id"] for c in listed["checks"]] == ["load.rows", "total.reconciles", "weighted.differs"]
    matrix = project.gate("--matrix").stdout
    assert "| F2 |" in matrix and "weighted.differs" in matrix


def test_missing_deliverable_fails_as_a_deliverable_problem(project):
    run = project.gate("app", "--json")
    assert run.returncode == 1
    data = last_json(run.stdout)
    assert data["status"] == "fail" and all(not c["ok"] for c in data["checks"])
    assert "setup failed" in data["checks"][0]["message"]


def test_good_and_broken_deliverables(project):
    from conftest import DEAD_LOOKUP, GOOD
    project.write("app/report.py", GOOD)
    assert project.gate("app").returncode == 0
    project.write("app/report.py", DEAD_LOOKUP)
    run = project.gate("app", "--json")
    assert run.returncode == 1
    failed = [c["id"] for c in last_json(run.stdout)["checks"] if not c["ok"]]
    assert failed == ["weighted.differs"]
    assert "stage-probability lookup" in run.stdout  # a message someone can act on


def test_only_runs_a_subset_and_rejects_unknown_ids(project):
    from conftest import DEAD_LOOKUP
    project.write("app/report.py", DEAD_LOOKUP)
    assert project.gate("app", "--only", "load.rows,total.reconciles").returncode == 0
    bad = project.gate("app", "--only", "no.such.check", "--json")
    assert bad.returncode == 3 and "HARNESS ERROR" in bad.stdout
    assert last_json(bad.stdout)["status"] == "harness_error"


def test_environment_problem_is_a_harness_error_not_a_failure(project):
    (project.root / "data/deals.csv").unlink()
    run = project.gate("app")
    assert run.returncode == 3
    assert "HARNESS ERROR" in run.stdout and "not a deliverable problem" in run.stdout


def test_no_arguments_is_a_harness_error(project):
    assert project.gate().returncode == 3


def test_selftest_fails_when_a_failure_mode_is_not_really_caught(project):
    # Weaken the F2 check so the broken fixture slips through.
    src = project.read("verify/smoke_test.py").replace("0 < weighted < total", "weighted <= total")
    project.write("verify/smoke_test.py", src)
    run = project.gate("--selftest")
    assert run.returncode == 1
    assert "SELFTEST DEFECT" in run.stdout and "F2" in run.stdout and "PASSED every check" in run.stdout


def test_selftest_fails_when_the_wrong_check_catches_it(project):
    src = project.read("verify/smoke_test.py").replace(
        '@gate.check("weighted.differs", catches=["F2"]', '@gate.check("weighted.differs", why="x", catches=[]')
    project.write("verify/smoke_test.py", src)
    run = project.gate("--selftest")
    assert run.returncode == 1 and "no check that catches it" in run.stdout


def test_a_check_must_say_what_it_catches(project):
    project.write("verify/smoke_test.py", project.read("verify/smoke_test.py").replace(
        '@gate.check("load.rows", catches=["F1"],', '@gate.check("load.rows",'))
    run = project.gate("--list")
    assert run.returncode != 0 and "names no failure mode" in run.stderr


# ------------------------------------- slow checks, bands and determinism --

def test_ml_example_gate_discriminates_and_reports_timing(ml_project):
    run = ml_project.gate("--selftest")
    assert run.returncode == 0, run.stdout + run.stderr
    for mode, check in (("F1", "noise.no_signal"), ("F2", "leak.flagged"),
                        ("F3", "rows.reconcile"), ("F4", "signal.detected")):
        assert f"{mode} caught by {check}" in run.stdout
    assert "TIMING: full gate" in run.stdout and "1 slow check(s) skipped per edit" in run.stdout
    assert "passes twice with identical results" in run.stdout
    listed = last_json(ml_project.gate("--list", "--json").stdout)
    assert [c["id"] for c in listed["checks"] if c["slow"]] == ["noise.no_signal"]


def test_fast_profile_skips_slow_checks_and_the_full_run_does_not(ml_project):
    from conftest import ml_sources
    _, broken = ml_sources()
    ml_project.write("app/profiler.py", broken["F1"])       # only the slow check can see F1
    full = ml_project.gate("app", "--json")
    assert full.returncode == 1
    assert [c["id"] for c in last_json(full.stdout)["checks"] if not c["ok"]] == ["noise.no_signal"]
    assert "expected between -0.2 and 0.2" in full.stdout   # a band, with the measured value
    fast = ml_project.gate("app", "--fast", "--json")
    assert fast.returncode == 0 and "SKIP noise.no_signal" in fast.stdout
    assert last_json(fast.stdout)["skipped_slow"] == ["noise.no_signal"]
    only_slow = ml_project.gate("app", "--fast", "--only", "noise.no_signal")
    assert only_slow.returncode == 0 and "GATE: PASS (0 checks)" in only_slow.stdout


def test_checks_report_how_long_they_took(ml_project):
    from conftest import ml_sources
    ml_project.write("app/profiler.py", ml_sources()[0])
    data = last_json(ml_project.gate("app", "--json").stdout)
    assert all(isinstance(c["seconds"], float) for c in data["checks"])


def test_selftest_catches_a_gate_whose_measurements_drift(project):
    src = project.read("verify/smoke_test.py").replace(
        "    rows = ctx.state[\"report\"].load(ctx.state[\"data_path\"])\n    want = len(",
        "    import random\n    ctx.record(\"unseeded score\", random.random())\n"
        "    rows = ctx.state[\"report\"].load(ctx.state[\"data_path\"])\n    want = len(")
    assert "unseeded score" in src
    project.write("verify/smoke_test.py", src)
    run = project.gate("--selftest")
    assert run.returncode == 1
    assert "NOT DETERMINISTIC" in run.stdout and "unseeded score" in run.stdout
    assert "Pin every seed" in run.stdout


def test_selftest_catches_a_gate_that_changes_its_verdict(project):
    flaky = '''

@gate.check("flaky.check", why="demonstration", doc="fails every other run")
def flaky_check(ctx):
    marker = ctx.artifacts / "flaky.count"
    ctx.artifacts.mkdir(parents=True, exist_ok=True)
    n = int(marker.read_text()) if marker.exists() else 0
    marker.write_text(str(n + 1))
    ctx.require(n % 2 == 0, "odd run")
'''
    src = project.read("verify/smoke_test.py").replace(
        "# ------------------------------------------------------------- fixtures --",
        flaky + "\n# fixtures")
    assert "flaky.check" in src
    project.write("verify/smoke_test.py", src)
    run = project.gate("--selftest")
    assert run.returncode == 1 and "failed different checks" in run.stdout
