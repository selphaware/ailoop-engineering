"""The guard's rules: what may be written, in which stage."""
import pytest

import policy

WIN = r"E:\CODE\proj"
NIX = "/work/proj"


@pytest.mark.parametrize("path,root,expected", [
    (r"E:\CODE\proj\verify\smoke_test.py", WIN, "verify/smoke_test.py"),
    (r"e:\code\PROJ\Verify\x.py", WIN, "Verify/x.py"),            # Windows ignores case
    ("/e/CODE/proj/app/main.py", WIN, "app/main.py"),             # Git Bash spelling
    (r"E:\CODE\proj", WIN, ""),
    (r"E:\CODE\projects\x.py", WIN, None),                        # prefix, not inside
    (r"C:\Windows\x", WIN, None),
    (r"E:\CODE\proj\app\..\verify\x.py", WIN, "verify/x.py"),     # .. cannot escape the lock
    ("/work/proj/tests/test_a.py", NIX, "tests/test_a.py"),
    ("/work/other/x", NIX, None),
])
def test_rel_posix(path, root, expected):
    assert policy.rel_posix(path, root) == expected


def test_relative_path_uses_cwd():
    assert policy.rel_posix("smoke_test.py", NIX, cwd="/work/proj/verify") == "verify/smoke_test.py"


@pytest.mark.parametrize("rel,kind", [
    ("verify/smoke_test.py", "judge"), ("verify/gatekit.py", "kit"), ("plan/tasks.json", "judge"),
    ("spec.md", "judge"), ("CLAUDE.md", "judge"), ("claude.md", "judge"),
    ("tests/test_a.py", "tests"), ("tests/pytest.ini", "kit"), ("loop/run_loop.py", "kit"),
    (".claude/hooks/guard.py", "kit"), (".claude/settings.json", "kit"),
    (".claude/skills/build/SKILL.md", "judge"), ("conftest.py", "rootlock"),
    ("app/conftest.py", "app"), ("app/tests/helper.py", "app"), ("app/main.py", "app"),
    ("verifying/x.py", "app"), ("specs.md", "app"),
])
def test_classify(rel, kind):
    assert policy.classify(rel) == kind


@pytest.mark.parametrize("stage,rel,allowed", [
    ("harness", "verify/smoke_test.py", True), ("harness", "plan/tasks.json", True),
    ("harness", "loop/run_loop.py", False), ("harness", ".claude/hooks/guard.py", False),
    ("harness", "verify/gatekit.py", False),
    ("tests", "tests/test_a.py", True), ("tests", "tests/fixtures/a.csv", True),
    ("tests", "tests/pytest.ini", False), ("tests", "app/main.py", False),
    ("tests", "verify/smoke_test.py", False), ("tests", "spec.md", False),
    ("build", "app/main.py", True), ("build", "requirements.txt", True),
    ("build", "tests/test_a.py", False), ("build", "verify/smoke_test.py", False),
    ("build", "plan/tasks.json", False), ("build", "spec.md", False),
    ("build", "conftest.py", False), ("build", "sitecustomize.py", False),
    ("build", ".claude/settings.json", False), ("build", "loop/loop.json", False),
    ("review", "app/main.py", False), ("review", "notes.md", False),
])
def test_file_write_by_stage(stage, rel, allowed):
    ok, reason = policy.check_file_write(f"{NIX}/{rel}", stage, NIX)
    assert ok is allowed
    if not allowed:
        assert "BLOCKED" in reason


def test_windows_backslash_paths_are_locked_too():
    ok, _ = policy.check_file_write(r"E:\CODE\proj\verify\smoke_test.py", "build", WIN)
    assert not ok
    ok, _ = policy.check_file_write(r"E:\CODE\proj\app\main.py", "build", WIN)
    assert ok


def test_outside_project_is_left_to_claude_code_in_build_but_blocked_in_review():
    assert policy.check_file_write("/tmp/x.txt", "build", NIX)[0]
    assert not policy.check_file_write("/tmp/x.txt", "review", NIX)[0]


ALLOWED_SHELL = [
    r"E:\envs\p\Scripts\python.exe verify\smoke_test.py app --only load.rows",
    "python -m pytest -c tests/pytest.ini --rootdir . -q tests/test_load.py",
    "python -m pytest tests/test_load.py > out.txt",
    "python -m pip install -r requirements.txt",
    "pip install git+https://github.com/org/repo.git",
    "cat .gitignore",
    "ls .git",
    "Get-Content verify\\smoke_test.py",
    "cp verify/fixtures/sample.csv app/sample.csv",           # copying OUT of a locked dir
    "Copy-Item -Path tests\\fixtures\\a.csv -Destination app\\a.csv",
    "Remove-Item app\\tmp.txt",
    "rm -rf app/__pycache__",
    "python app/main.py --input data/deals.csv > app/out.json",
    'python -c "import app.report as r; print(r.total([]))"',
    "echo done",
]

BLOCKED_SHELL = [
    "git status",
    "git commit -am wip",
    'cd app && git add -A',
    '"C:\\Program Files\\Git\\cmd\\git.exe" log',
    "/usr/bin/git diff",
    "python loop/run_loop.py build",
    "python ..\\kit\\install_kit.py .",
    "rm verify/smoke_test.py",
    "Remove-Item -Recurse tests",
    "mv tests/test_load.py tests/old.py",
    "echo pass > verify/smoke_test.py",
    "echo x >> tests\\test_load.py",
    "Set-Content -Path plan\\tasks.json -Value '{}'",
    "'x' | Out-File spec.md",
    "cp app/fake_gate.py verify/smoke_test.py",
    "Copy-Item -Path app\\x.py -Destination tests\\test_load.py",
    "python -c \"open('verify/smoke_test.py','w').write('')\"",
    "python -c \"import pathlib; pathlib.Path('tests/test_load.py').write_text('')\"",
    "sed -i s/assert/pass/ tests/test_load.py",
    "echo x > conftest.py",
    "echo {} > .claude/settings.json",
    r"del E:\CODE\proj\verify\smoke_test.py",
]


@pytest.mark.parametrize("command", ALLOWED_SHELL)
def test_shell_allowed_in_build(command):
    ok, reason = policy.check_shell(command, "build", WIN)
    assert ok, reason


@pytest.mark.parametrize("command", BLOCKED_SHELL)
def test_shell_blocked_in_build(command):
    ok, reason = policy.check_shell(command, "build", WIN)
    assert not ok
    assert "BLOCKED" in reason


def test_harness_stage_may_write_the_gate_through_the_shell_but_not_the_kit():
    assert policy.check_shell("echo x > verify/notes.txt", "harness", NIX)[0]
    assert not policy.check_shell("echo x > loop/loop.json", "harness", NIX)[0]
    assert not policy.check_shell("git init", "harness", NIX)[0]


def test_unknown_stage_falls_back_to_the_strict_policy(monkeypatch):
    monkeypatch.setenv("LOOP_STAGE", "nonsense")
    assert policy.current_stage() == "build"
    monkeypatch.delenv("LOOP_STAGE")
    assert policy.current_stage() == "build"


@pytest.mark.parametrize("command,allowed", [
    (r"E:\envs\p\Scripts\python.exe loop\run_loop.py doctor", True),
    ("python loop/run_loop.py build --dry-run", True),
    (r'& "A:\envs\my proj\Scripts\python.exe" loop\run_loop.py doctor', True),   # PowerShell call operator
    ("python loop/run_loop.py status", True),
    ("python loop/run_loop.py doctor --live", False),      # spends money
    ("python loop/run_loop.py build", False),
    ("python loop/run_loop.py go", False),
    ("python loop/run_loop.py doctor; python loop/run_loop.py build", False),
    ("python loop/run_loop.py doctor && echo x > loop/loop.json", False),
])
def test_harness_stage_may_run_only_the_drivers_read_only_checks(command, allowed):
    assert policy.check_shell(command, "harness", WIN)[0] is allowed
    assert not policy.check_shell(command, "build", WIN)[0]     # never during a build


def test_a_virtual_environment_inside_the_project_is_never_walked(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("x = 1\n")
    site = tmp_path / "mlprof_env" / "Lib" / "site-packages" / "pytest"
    site.mkdir(parents=True)
    (site / "__init__.py").write_text("import sys\n")
    (tmp_path / "mlprof_env" / "pyvenv.cfg").write_text("home = x\n")
    assert [rel for rel, _ in policy.iter_files(tmp_path)] == ["app/main.py"]
