import sys
import time

from scripts.scan_jobs import ScanJobManager


def wait_for_terminal(manager, job_id, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = manager.get(job_id)
        if job["status"] in {"completed", "failed", "cancelled"}:
            return job
        time.sleep(0.02)
    raise AssertionError("background job did not finish in time")


def make_project(tmp_path, source):
    (tmp_path / "main.py").write_text(source, encoding="utf-8")
    return tmp_path


def test_background_job_captures_output_and_exit_code(tmp_path):
    project = make_project(
        tmp_path,
        "print('scan-started', flush=True)\nprint('scan-finished', flush=True)\n",
    )
    manager = ScanJobManager()
    job_id = manager.start(project)
    job = wait_for_terminal(manager, job_id)

    assert job["status"] == "completed"
    assert job["return_code"] == 0
    assert job["output"] == ["scan-started", "scan-finished"]
    assert job["finished_at"] is not None


def test_background_job_reports_failure(tmp_path):
    project = make_project(tmp_path, "raise SystemExit(7)\n")
    manager = ScanJobManager()
    job = wait_for_terminal(manager, manager.start(project))

    assert job["status"] == "failed"
    assert job["return_code"] == 7


def test_cancel_running_job(tmp_path):
    project = make_project(
        tmp_path,
        "import time\nprint('ready', flush=True)\ntime.sleep(30)\n",
    )
    manager = ScanJobManager()
    job_id = manager.start(project)

    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        current = manager.get(job_id)
        if current["output"]:
            break
        time.sleep(0.02)

    assert manager.cancel(job_id) is True
    job = wait_for_terminal(manager, job_id)
    assert job["status"] == "cancelled"
    assert job["cancel_requested"] is True


def test_custom_cidr_requires_exact_authorization(tmp_path):
    project = make_project(tmp_path, "print('should-not-run')\n")
    manager = ScanJobManager()

    try:
        manager.start(project, scan_cidr="192.168.20.0/24", approved=True,
                      confirmation="192.168.2.0/24")
    except ValueError as exc:
        assert "exact confirmation" in str(exc)
    else:
        raise AssertionError("invalid CIDR confirmation was accepted")


def test_missing_entry_point_is_reported(tmp_path):
    manager = ScanJobManager()
    try:
        manager.start(tmp_path)
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("missing main.py was accepted")


def test_rejects_overlapping_scan_jobs(tmp_path):
    project = make_project(
        tmp_path,
        "import time\\ntime.sleep(2)\\n",
    )
    manager = ScanJobManager()
    first = manager.start(project)
    try:
        manager.start(project)
    except RuntimeError as exc:
        assert "already active" in str(exc)
    else:
        raise AssertionError("overlapping scan was accepted")
    manager.cancel(first)
    assert wait_for_terminal(manager, first)["status"] == "cancelled"
