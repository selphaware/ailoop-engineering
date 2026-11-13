"""The three hooks, invoked the way Claude Code invokes them."""
import json

from conftest import DEAD_LOOKUP, GOOD


def write_payload(project, rel, tool="Write"):
    return {"hook_event_name": "PreToolUse", "tool_name": tool, "cwd": str(project.root),
            "tool_input": {"file_path": str(project.root / rel), "content": "x"}}


# ------------------------------------------------------------------ guard --

def test_guard_blocks_the_gate_and_allows_the_app(project):
    blocked = project.hook("guard.py", write_payload(project, "verify/smoke_test.py"))
    assert blocked.returncode == 2 and "BLOCKED" in blocked.stderr
    assert project.hook("guard.py", write_payload(project, "app/report.py", "Edit")).returncode == 0


def test_guard_is_stage_aware(project):
    gate = write_payload(project, "verify/smoke_test.py")
    assert project.hook("guard.py", gate, LOOP_STAGE="harness").returncode == 0
    assert project.hook("guard.py", gate, LOOP_STAGE="tests").returncode == 2
    test = write_payload(project, "tests/test_new.py")
    assert project.hook("guard.py", test, LOOP_STAGE="tests").returncode == 0
    assert project.hook("guard.py", test, LOOP_STAGE="build").returncode == 2
    assert project.hook("guard.py", write_payload(project, "app/x.py"), LOOP_STAGE="review").returncode == 2


def test_guard_blocks_git_and_shell_writes_to_the_judge(project):
    def shell(command, tool="Bash"):
        return project.hook("guard.py", {"tool_name": tool, "cwd": str(project.root),
                                         "tool_input": {"command": command}})
    assert shell("git commit -am x").returncode == 2
    assert shell("Set-Content verify\\smoke_test.py ''", "PowerShell").returncode == 2
    assert shell("python verify/smoke_test.py app").returncode == 0
    assert shell("python loop/run_loop.py build").returncode == 2


def test_guard_ignores_read_tools(project):
    assert project.hook("guard.py", {"tool_name": "Read", "tool_input": {
        "file_path": str(project.root / "verify/smoke_test.py")}}).returncode == 0


def test_guard_fails_closed_and_says_it_is_not_the_codes_fault(project):
    (project.root / "loop/policy.py").write_text("raise RuntimeError('boom')\n")
    run = project.hook("guard.py", write_payload(project, "app/report.py"))
    assert run.returncode == 2 and "HARNESS ERROR" in run.stderr


# -------------------------------------------------------------- gate hook --

EDIT = {"hook_event_name": "PostToolUse", "tool_name": "Edit", "tool_input": {"file_path": "app/report.py"}}


def test_gate_hook_feeds_a_failure_back_with_exit_2(project):
    project.write("app/report.py", DEAD_LOOKUP)
    run = project.hook("gate_hook.py", EDIT)
    assert run.returncode == 2
    assert "weighted.differs" in run.stderr and "Fix the deliverable, not the gate" in run.stderr


def test_gate_hook_is_silent_when_the_gate_passes(project):
    project.write("app/report.py", GOOD)
    run = project.hook("gate_hook.py", EDIT)
    assert run.returncode == 0 and run.stderr == ""


def test_gate_hook_only_judges_the_current_tasks_checks(project):
    project.write("app/report.py", DEAD_LOOKUP)
    accept = json.dumps({"gate": ["load.rows"], "tests": []})
    assert project.hook("gate_hook.py", EDIT, LOOP_STAGE="build", LOOP_ACCEPT=accept).returncode == 0
    accept = json.dumps({"gate": ["weighted.differs"], "tests": []})
    assert project.hook("gate_hook.py", EDIT, LOOP_STAGE="build", LOOP_ACCEPT=accept).returncode == 2


def test_gate_hook_stays_out_of_the_way_outside_the_build_stage(project):
    for stage in ("harness", "tests", "review"):
        assert project.hook("gate_hook.py", EDIT, LOOP_STAGE=stage).returncode == 0


def test_gate_hook_never_blames_the_code_for_a_harness_error(project):
    project.write("app/report.py", GOOD)
    (project.root / "data/deals.csv").unlink()          # environment problem
    run = project.hook("gate_hook.py", EDIT)
    assert run.returncode == 0
    assert "HARNESS ERROR" in json.loads(run.stdout)["systemMessage"]


def test_gate_hook_does_nothing_before_a_plan_exists(project):
    (project.root / "plan/tasks.json").unlink()
    assert project.hook("gate_hook.py", EDIT).returncode == 0


# -------------------------------------------------------------- stop hook --

STOP = {"hook_event_name": "Stop", "session_id": "s1", "stop_hook_active": False}


def test_stop_hook_does_nothing_in_a_plain_interactive_session(project):
    project.write("app/report.py", DEAD_LOOKUP)
    assert project.hook("stop_gate.py", STOP).returncode == 0


def test_stop_hook_blocks_a_failing_build_run_then_hands_over_to_the_driver(project):
    project.write("app/report.py", DEAD_LOOKUP)
    codes = [project.hook("stop_gate.py", STOP, LOOP_STAGE="build").returncode for _ in range(4)]
    assert codes == [2, 2, 2, 0]      # three nudges, then the driver judges
    other = dict(STOP, session_id="s2")
    assert project.hook("stop_gate.py", other, LOOP_STAGE="build").returncode == 2


def test_stop_hook_reports_failing_tests_too(project):
    project.write("app/__init__.py", "")
    project.write("app/report.py", DEAD_LOOKUP)
    accept = json.dumps({"gate": ["load.rows"], "tests": ["tests/test_totals.py"]})
    run = project.hook("stop_gate.py", STOP, LOOP_STAGE="build", LOOP_ACCEPT=accept)
    assert run.returncode == 2
    assert "test_f2_weighted_is_below_total" in run.stderr and "Gate checks failing" not in run.stderr


def test_stop_hook_allows_stopping_when_everything_passes(project):
    project.write("app/__init__.py", "")
    project.write("app/report.py", GOOD)
    assert project.hook("stop_gate.py", STOP, LOOP_STAGE="build").returncode == 0
