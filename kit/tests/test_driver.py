"""The driver end to end, against a fake `claude` command.

These tests prove the loop's own logic: routing, escalation, the tamper
check, the stop conditions. They cannot prove that the real Claude Code
accepts every flag; `run_loop.py doctor --live` does that on your machine.
"""
import copy
import json
import subprocess

from conftest import DEAD_LOOKUP, EMPTY_LOADER, GOOD, HAPPY, LOADER, STUB, TESTS


def build_calls(project):
    return [(c["task"], c["model"]) for c in project.calls() if c["stage"] == "build"]


# ---------------------------------------------------------------- routing --

def test_each_task_runs_on_the_model_its_tier_names(project):
    run = project.drive("build", scenario=HAPPY)
    assert run.returncode == 0, run.stdout + run.stderr
    assert build_calls(project) == [("T1", "haiku"), ("T2", "sonnet"), ("T3", "opus")]
    state = project.state()
    assert state["build_passed"] is True
    assert {t: r["model_used"] for t, r in state["tasks"].items()} == {
        "T1": "haiku", "T2": "sonnet", "T3": "opus"}
    assert state["spent_usd"] == 0.75
    report = project.read("loop/state/build-report.md")
    assert "Result: PASS" in report and "| T2 | routine | sonnet | 1 |" in report


def test_runs_are_unattended_capped_and_labelled_for_the_hooks(project):
    project.drive("build", scenario=HAPPY)
    call = project.calls()[1]
    assert call["permission_mode"] == "auto" and call["max_turns"] == "100"
    assert ["--permission-prompts", "none"] == call["argv"][call["argv"].index("--permission-prompts"):][:2]
    assert call["effort"] == "medium" and call["advisor"] is None
    assert "# Role: builder" in call["prompt"] and "# Task T2: CSV loader" in call["prompt"]
    assert "--only load.rows" in call["prompt"]


def test_earlier_checks_ratchet_into_later_tasks(project):
    project.drive("build", scenario=HAPPY)
    accept = json.loads(project.calls()[2]["accept"])          # T3
    assert accept["gate"] == ["load.rows", "total.reconciles", "weighted.differs"]
    assert accept["tests"] == ["tests/test_load.py", "tests/test_skeleton.py", "tests/test_totals.py"]
    assert "Must stay green" in project.calls()[2]["prompt"]


def test_dry_run_shows_the_routing_and_runs_nothing(project):
    run = project.drive("build", "--dry-run", scenario=HAPPY)
    assert run.returncode == 0
    assert "sonnet x2 -> opus x3" in run.stdout and "haiku x2 -> sonnet x2 -> opus x3" in run.stdout
    assert project.calls() == []


def test_optional_advisor_is_set_per_tier(project):
    cfg = json.loads(project.read("loop/loop.json"))
    cfg["tiers"]["complex"]["advisor"] = "fable"
    project.write("loop/loop.json", json.dumps(cfg))
    project.drive("build", scenario=HAPPY)
    assert [c["advisor"] for c in project.calls()] == [None, None, "fable"]   # opus tier only


# ------------------------------------------------------------- escalation --

def test_a_task_escalates_to_the_next_tier_after_its_attempts(project):
    scenario = copy.deepcopy(HAPPY)
    scenario["build:T2:sonnet"] = [{"write": {"app/report.py": EMPTY_LOADER}}]
    scenario["build:T2:opus"] = [{"write": {"app/report.py": LOADER}}]
    run = project.drive("build", scenario=scenario)
    assert run.returncode == 0, run.stdout
    t2 = [c for c in project.calls() if c["task"] == "T2"]
    assert [c["model"] for c in t2] == ["sonnet", "sonnet", "opus"]
    assert t2[0]["resume"] is None
    assert t2[1]["resume"] is not None            # a retry on the same tier keeps its context
    assert t2[2]["resume"] is None                # a stronger model starts clean
    assert "previous attempt did not pass" in t2[2]["prompt"] and "load.rows" in t2[2]["prompt"]
    record = project.state()["tasks"]["T2"]
    assert record["model_used"] == "opus" and record["tier_used"] == "complex"
    assert "Escalated above their planned tier: T2" in project.read("loop/state/build-report.md")


def test_three_strikes_at_the_top_tier_stops_and_asks_fable_for_a_diagnosis(project):
    scenario = copy.deepcopy(HAPPY)
    scenario["build:T3:opus"] = [{"write": {"app/report.py": DEAD_LOOKUP}}]
    scenario["review:T3:fable"] = [{"result": "CAUSE: SPEC\n\nSection 2.2 gives no table."}]
    run = project.drive("build", scenario=scenario)
    assert run.returncode == 2
    assert "STOPPED - needs you" in run.stdout
    assert build_calls(project).count(("T3", "opus")) == 3
    diagnose = project.calls()[-1]
    assert (diagnose["stage"], diagnose["model"]) == ("review", "fable")   # read-only stage
    packet = project.read("loop/state/escalations/T3.md")
    assert "SAME checks" in packet and "CAUSE: SPEC" in packet
    assert project.state()["tasks"]["T3"]["status"] == "failed"
    assert "NOT PASSING" in project.read("loop/state/build-report.md")


def test_a_stopped_build_resumes_where_it_left_off(project):
    scenario = copy.deepcopy(HAPPY)
    scenario["build:T3:opus"] = [{"write": {"app/report.py": DEAD_LOOKUP}}]
    assert project.drive("build", scenario=scenario).returncode == 2
    project.log.unlink()
    run = project.drive("build", scenario=HAPPY)
    assert run.returncode == 0
    assert build_calls(project) == [("T3", "opus")]      # T1 and T2 were not repeated


def test_tasks_that_pass_alone_but_not_together_get_an_integration_task(project):
    plan = json.loads(project.read("plan/tasks.json"))
    plan["tasks"][2].update(gate_checks=["total.reconciles"], tests=[])   # nobody owns F2 now
    project.write("plan/tasks.json", json.dumps(plan))
    scenario = copy.deepcopy(HAPPY)
    scenario["build:T3:opus"] = [{"write": {"app/report.py": DEAD_LOOKUP}}]
    scenario["build:INTEGRATION:opus"] = [{"write": {"app/report.py": GOOD}}]
    run = project.drive("build", scenario=scenario)
    assert run.returncode == 0, run.stdout
    assert build_calls(project)[-1] == ("INTEGRATION", "opus")
    assert "weighted.differs" in project.calls()[-1]["prompt"]


# ---------------------------------------------------------------- tamper --

ALWAYS_PASS = 'import json, sys\nprint(json.dumps({"status": "pass", "checks": []}))\nsys.exit(0)\n'


def test_an_agent_that_rewrites_the_gate_is_caught_and_undone(project):
    original = project.read("verify/smoke_test.py")
    scenario = copy.deepcopy(HAPPY)
    scenario["build:T2:sonnet"] = [
        {"write": {"app/report.py": EMPTY_LOADER, "verify/smoke_test.py": ALWAYS_PASS,
                   "conftest.py": "collect_ignore = ['tests']\n"}},
        {"write": {"app/report.py": LOADER}},
    ]
    run = project.drive("build", scenario=scenario)
    assert run.returncode == 0, run.stdout
    assert "TAMPER detected and undone" in run.stdout
    assert project.read("verify/smoke_test.py") == original
    assert not (project.root / "conftest.py").exists()
    attempts = project.state()["tasks"]["T2"]["attempts"]
    assert attempts[0]["passed"] is False and "modified verify/smoke_test.py" in attempts[0]["tamper"]
    retry = [c for c in project.calls() if c["task"] == "T2"][1]
    assert retry["resume"] is None                       # a tampering run does not keep its context
    assert "changed locked files" in retry["prompt"]


def test_an_agent_that_edits_a_test_to_pass_gains_nothing(project):
    scenario = copy.deepcopy(HAPPY)
    scenario["build:T3:opus"] = [{"write": {
        "app/report.py": DEAD_LOOKUP,
        "tests/test_totals.py": "def test_ok():\n    assert True\n",
        "verify/smoke_test.py": ALWAYS_PASS}}]
    run = project.drive("build", scenario=scenario)
    assert run.returncode == 2                            # still fails, three times
    assert project.read("tests/test_totals.py") == TESTS["tests/test_totals.py"]


# ----------------------------------------------------- stops and failures --

def test_a_run_that_returns_nothing_is_a_harness_error_and_costs_no_attempt(project):
    scenario = {"build:*:*": [{"raw": "Error: not logged in", "rc": 1}]}
    run = project.drive("build", scenario=scenario)
    assert run.returncode == 3
    assert "HARNESS ERROR - this is not a code problem" in run.stdout and "doctor --live" in run.stdout
    assert project.state()["tasks"]["T1"]["attempts"] == []


def test_the_total_budget_stops_the_build(project):
    cfg = json.loads(project.read("loop/loop.json"))
    cfg["limits"]["total_budget_usd"] = 0.4
    project.write("loop/loop.json", json.dumps(cfg))
    run = project.drive("build", scenario=HAPPY)
    assert run.returncode == 2 and "total budget reached" in run.stdout
    assert build_calls(project) == [("T1", "haiku"), ("T2", "sonnet")]


def test_a_plan_that_names_a_check_the_gate_does_not_have_is_rejected(project):
    plan = json.loads(project.read("plan/tasks.json"))
    plan["tasks"][1]["gate_checks"] = ["load.rowz"]
    plan["tasks"][0]["tests"] = []
    project.write("plan/tasks.json", json.dumps(plan))
    run = project.drive("build", scenario=HAPPY)
    assert run.returncode == 3
    assert "gate check 'load.rowz' does not exist" in run.stdout
    assert "T1: no acceptance" in run.stdout and project.calls() == []


def test_build_refuses_to_start_without_the_planned_tests(bare_project):
    run = bare_project.drive("build", scenario=HAPPY)
    assert run.returncode == 2 and "run_loop.py tests" in run.stdout


def git(project, *args):
    return subprocess.run(["git", "-c", "user.email=t@example.com", "-c", "user.name=t", *args],
                          cwd=project.root, capture_output=True, text=True, check=True)


def test_build_requires_the_harness_to_be_committed(project):
    git(project, "init", "-q")
    git(project, "add", "-A")
    git(project, "commit", "-q", "-m", "harness")
    assert project.drive("build", "--dry-run", scenario=HAPPY).returncode == 0
    with (project.root / "verify/smoke_test.py").open("a") as fh:
        fh.write("# edited after review\n")
    run = project.drive("build", scenario=HAPPY)
    assert run.returncode == 2 and "uncommitted changes" in run.stdout and project.calls() == []
    assert project.drive("build", "--allow-dirty", scenario=HAPPY).returncode == 0


# ------------------------------------------------------------ tests stage --

def test_tests_stage_writes_a_suite_that_is_red_before_the_build(bare_project):
    scenario = {"tests:*:*": [{"write": TESTS}]}
    run = bare_project.drive("tests", scenario=scenario)
    assert run.returncode == 0, run.stdout
    call = bare_project.calls()[0]
    assert (call["model"], call["effort"]) == ("opus", "high")
    assert "# Role: test author" in call["prompt"] and "tests/test_totals.py" in call["prompt"]
    assert bare_project.state()["tests_written"] is True
    assert "Passing before the build: 0" in bare_project.read("loop/state/tests-report.md")


def test_tests_that_already_pass_are_listed_for_a_human_to_check(bare_project):
    tests = dict(TESTS)
    tests["tests/test_skeleton.py"] += "\ndef test_fixture_file_exists():\n    assert True\n"
    run = bare_project.drive("tests", scenario={"tests:*:*": [{"write": tests}]})
    assert run.returncode == 0
    report = bare_project.read("loop/state/tests-report.md")
    assert "ALREADY PASS" in report and "test_fixture_file_exists" in report


def test_a_suite_that_passes_with_no_application_is_rejected(bare_project):
    vacuous = {rel: "def test_nothing():\n    assert True\n" for rel in TESTS}
    run = bare_project.drive("tests", scenario={"tests:*:*": [{"write": vacuous}]})
    assert run.returncode == 2
    assert "PASSES before the application exists" in run.stdout
    assert len(bare_project.calls()) == 2 and bare_project.calls()[1]["resume"]


def test_the_test_author_may_not_write_application_code_or_skip_tests(bare_project):
    skipping = dict(TESTS)
    skipping["tests/test_load.py"] = "import pytest\n@pytest.mark.skip\ndef test_later():\n    pass\n"
    scenario = {"tests:*:*": [
        {"write": {**skipping, "app/report.py": STUB, "spec.md": "# rewritten\n"}},
        {"write": TESTS, "delete": ["app/report.py"]},
    ]}
    run = bare_project.drive("tests", scenario=scenario)
    assert run.returncode == 0, run.stdout
    assert "wrote outside tests/" in run.stdout and "Skipped or xfailed" in run.stdout
    assert "modified spec.md" in run.stdout and bare_project.read("spec.md") == "# Spec\n"


# ----------------------------------------------------------------- review --

def test_review_runs_read_only_on_fable_and_records_the_verdict(project):
    project.drive("build", scenario=HAPPY)
    run = project.drive("review")
    assert run.returncode == 0 and "Verdict: SHIP" in run.stdout
    call = project.calls()[-1]
    assert (call["stage"], call["model"]) == ("review", "fable")
    assert "| F2 |" in call["prompt"] and "# Build report" in call["prompt"]
    assert project.read("loop/state/review.md").startswith("VERDICT: SHIP")


def test_a_review_that_does_not_say_ship_stops_for_a_human(project):
    scenario = copy.deepcopy(HAPPY)
    scenario["review:*:*"] = [{"result": "VERDICT: FIX FIRST\n\n| 1 | high | gate-gap | ..."}]
    project.drive("build", scenario=scenario)
    assert project.drive("review").returncode == 2


def test_a_reviewer_that_changes_files_is_reported(project):
    scenario = copy.deepcopy(HAPPY)
    scenario["review:*:*"] = [{"result": "VERDICT: SHIP", "write": {
        "app/report.py": GOOD + "\n# tidied\n", "verify/smoke_test.py": ALWAYS_PASS}}]
    original = project.read("verify/smoke_test.py")
    project.drive("build", scenario=scenario)
    run = project.drive("review")
    assert run.returncode == 2
    review = project.read("loop/state/review.md")
    assert "WARNING: the reviewer changed files" in review and "app/report.py" in review
    assert project.read("verify/smoke_test.py") == original


def test_judge_aware_application_code_is_flagged_for_the_reviewer(project):
    scenario = copy.deepcopy(HAPPY)
    scenario["build:T3:opus"] = [{"write": {"app/report.py": GOOD + (
        "\nimport os\nif os.environ.get('PYTEST_CURRENT_TEST'):\n    pass\n")}}]
    project.drive("build", scenario=scenario)
    report = project.read("loop/state/build-report.md")
    assert "Judge-awareness warnings" in report and "PYTEST_CURRENT_TEST" in report


# -------------------------------------------------------------- go/doctor --

def test_go_runs_tests_build_and_review_in_one_unattended_pass(bare_project):
    scenario = copy.deepcopy(HAPPY)
    scenario["tests:*:*"] = [{"write": TESTS}]
    run = bare_project.drive("go", scenario=scenario)
    assert run.returncode == 0, run.stdout
    assert [(c["stage"], c["model"]) for c in bare_project.calls()] == [
        ("tests", "opus"), ("build", "haiku"), ("build", "sonnet"), ("build", "opus"),
        ("review", "fable")]


def test_doctor_passes_on_a_healthy_project_and_can_make_a_live_call(project):
    run = project.drive("doctor", "--live",
                        scenario={"review:*:*": [{"result": "LOOP-OK Python 3.12.13"}]})
    assert run.returncode == 0, run.stdout
    for line in ("hooks registered with an absolute interpreter path", "gate self-test: SELFTEST: PASS",
                 "plan valid: 3 task(s)", "live call worked on haiku", "Doctor: OK"):
        assert line in run.stdout


def test_doctor_reports_a_missing_hook_and_a_broken_gate(project):
    settings = json.loads(project.read(".claude/settings.json"))
    del settings["hooks"]["Stop"]
    project.write(".claude/settings.json", json.dumps(settings))
    project.write("verify/smoke_test.py", project.read("verify/smoke_test.py").replace(
        "0 < weighted < total", "weighted <= total"))
    run = project.drive("doctor")
    assert run.returncode == 3
    assert "registers no Stop hook" in run.stdout and "gate self-test: SELFTEST: FAIL" in run.stdout


def test_status_summarises_progress(project):
    project.drive("build", scenario=HAPPY)
    out = project.drive("status").stdout
    assert "build passed: True" in out and "T2" in out and "on=sonnet" in out


def test_doctor_live_fails_when_commands_cannot_run_unattended(project):
    run = project.drive("doctor", "--live", scenario={"review:*:*": [{"result": "LOOP-OK"}]})
    assert run.returncode == 3 and "could not run a command" in run.stdout


def test_tests_added_after_a_build_may_pass_immediately(project):
    assert project.drive("build", scenario=HAPPY).returncode == 0
    plan = json.loads(project.read("plan/tasks.json"))
    plan["tasks"].append({"id": "T4", "title": "Row count helper", "tier": "support",
                          "depends_on": ["T3"], "brief": "Add count(rows).",
                          "tests": ["tests/test_count.py"], "gate_checks": []})
    project.write("plan/tasks.json", json.dumps(plan))
    assert "run_loop.py tests" in project.drive("build").stdout          # new test file is missing
    new_test = "def test_load_still_works():\n    from app import report\n    assert report.load\n"
    run = project.drive("tests", scenario={"tests:*:*": [{"write": {"tests/test_count.py": new_test}}]})
    assert run.returncode == 0, run.stdout
    assert "test_load_still_works" in project.read("loop/state/tests-report.md")


# ------------------------------------------------- slow checks and timing --

def test_the_driver_judges_slow_checks_the_per_edit_hook_skipped(ml_project):
    from conftest import ml_sources
    good, broken = ml_sources()
    scenario = {"build:T1:opus": [{"write": {"app/profiler.py": broken["F1"]}},
                                  {"write": {"app/profiler.py": good}}]}
    run = ml_project.drive("build", scenario=scenario)
    assert run.returncode == 0, run.stdout
    attempts = ml_project.state()["tasks"]["T1"]["attempts"]
    assert [a["passed"] for a in attempts] == [False, True]
    assert attempts[0]["signature"] == "gate:noise.no_signal|tests:"
    prompt = ml_project.calls()[0]["prompt"]
    assert "`noise.no_signal`" in prompt and "(slow: not run on each edit" in prompt
    assert "lift on the pure-noise data" in ml_project.calls()[1]["prompt"]
    # No tests/ in this project: the build says so instead of failing or staying quiet.
    assert "there is no test suite" in run.stdout
    assert "full gate ONLY" in ml_project.read("loop/state/build-report.md")


def test_doctor_reports_gate_timing_and_warns_when_the_per_edit_run_is_too_slow(ml_project):
    run = ml_project.drive("doctor")
    assert "gate timing:" in run.stdout and "per edit" in run.stdout
    cfg = json.loads(ml_project.read("loop/loop.json"))
    cfg["limits"]["hook_gate_budget_sec"] = -1
    ml_project.write("loop/loop.json", json.dumps(cfg))
    run = ml_project.drive("doctor")
    assert "on every edit (budget -1s)" in run.stdout and "slow=True" in run.stdout


def test_doctor_names_a_nondeterministic_gate(project):
    project.write("verify/smoke_test.py", project.read("verify/smoke_test.py").replace(
        "    want = len(ctx.state[\"source\"])\n    ctx.require(len(rows) == want,",
        "    import random\n    ctx.record(\"unseeded\", random.random())\n"
        "    want = len(ctx.state[\"source\"])\n    ctx.require(len(rows) == want,"))
    run = project.drive("doctor")
    assert run.returncode == 3
    assert "gate self-test: SELFTEST: FAIL" in run.stdout and "NOT DETERMINISTIC" in run.stdout
