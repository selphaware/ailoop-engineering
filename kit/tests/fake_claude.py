"""A stand-in for the `claude` command, for testing the driver offline.

It reads a scenario file (FAKE_SCENARIO) keyed by "stage:task:model", performs
the scripted file writes, and prints the JSON a real `claude -p
--output-format json` run would print. Every call is appended to FAKE_LOG so
tests can assert which model ran which task.
"""
import json
import os
import sys
from pathlib import Path


def main() -> int:
    argv = sys.argv[1:]
    if "--version" in argv:
        print("2.9.9 (Claude Code)")
        return 0

    def opt(name):
        return argv[argv.index(name) + 1] if name in argv else None

    prompt = sys.stdin.read() if "-p" in argv else ""
    stage, task = os.environ.get("LOOP_STAGE", ""), os.environ.get("LOOP_TASK", "")
    model = opt("--model")
    scenario_path = Path(os.environ["FAKE_SCENARIO"])
    scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
    count_path = scenario_path.with_suffix(".count")
    counts = json.loads(count_path.read_text()) if count_path.exists() else {}
    key = next((k for k in (f"{stage}:{task}:{model}", f"{stage}:{task}:*", f"{stage}:*:*")
                if k in scenario), None)
    actions = scenario.get(key) or [{}]
    index = counts.get(key or "", 0)
    counts[key or ""] = index + 1
    count_path.write_text(json.dumps(counts))
    action = actions[min(index, len(actions) - 1)]

    with open(os.environ["FAKE_LOG"], "a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "stage": stage, "task": task, "model": model, "effort": opt("--effort"),
            "resume": opt("--resume"), "permission_mode": opt("--permission-mode"),
            "max_turns": opt("--max-turns"), "advisor": opt("--advisor"),
            "accept": os.environ.get("LOOP_ACCEPT"), "prompt": prompt, "argv": argv,
        }) + "\n")

    for rel, content in (action.get("write") or {}).items():
        target = Path.cwd() / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    for rel in action.get("delete") or []:
        (Path.cwd() / rel).unlink(missing_ok=True)

    if "raw" in action:  # simulate a run that returned nothing usable
        sys.stdout.write(action["raw"])
        return action.get("rc", 1)
    print(json.dumps({
        "type": "result", "subtype": action.get("subtype", "success"),
        "is_error": action.get("is_error", False), "num_turns": action.get("turns", 3),
        "result": action.get("result", "done"),
        "session_id": f"sess-{sum(counts.values())}",
        "total_cost_usd": action.get("cost", 0.25),
    }))
    return action.get("rc", 0)


if __name__ == "__main__":
    sys.exit(main())
