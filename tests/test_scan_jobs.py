import os
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


def test_progress_parser_tracks_stage_and_target_counts():
    job = {
        "progress": 0.0,
        "stage": "Sırada",
        "completed_targets": 0,
        "total_targets": 0,
    }

    ScanJobManager._update_progress(job, "[1/4] Aktif ag algilaniyor...")
    assert job["stage"] == "Ağ algılanıyor"
    assert job["progress"] == 0.0

    ScanJobManager._update_progress(job, "[2/4] 100 IP adresi taraniyor")
    ScanJobManager._update_progress(job, "Tarama: 50/100")
    assert job["stage"] == "Cihazlar taranıyor"
    assert job["completed_targets"] == 50
    assert job["total_targets"] == 100
    assert 0.5 < job["progress"] < 0.6

    ScanJobManager._update_progress(job, "Tarama tamamlandi. Bulunan cihaz: 12")
    assert job["stage"] == "Tamamlandı"
    assert job["progress"] == 1.0


def test_job_manager_uses_structured_progress_events():
    import json

    from scripts.scan_events import EVENT_PREFIX

    job = {
        "progress": 0.0,
        "stage": "Sırada",
        "progress_message": "",
        "completed_targets": 0,
        "total_targets": 0,
    }
    event = {
        "type": "progress",
        "stage": "Ağ topolojisi",
        "progress": 0.72,
        "message": "Topoloji ilişkileri hesaplanıyor",
    }

    ScanJobManager._update_progress(job, EVENT_PREFIX + json.dumps(event))

    assert job["stage"] == "Ağ topolojisi"
    assert job["progress"] == 0.72
    assert job["progress_message"] == "Topoloji ilişkileri hesaplanıyor"



def _process_is_running(pid):
    if sys.platform.startswith("linux"):
        stat_path = f"/proc/{pid}/stat"
        try:
            state = open(stat_path, encoding="utf-8").read().split(") ", 1)[1][0]
            return state != "Z"
        except FileNotFoundError:
            return False
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, OSError):
        return False


def test_cancel_running_job_terminates_child_processes(tmp_path):
    project = make_project(
        tmp_path,
        "import subprocess, sys, time\n"
        "child = subprocess.Popen([sys.executable, '-c', "
        "'import time; time.sleep(60)'])\n"
        "print(child.pid, flush=True)\n"
        "time.sleep(60)\n",
    )
    manager = ScanJobManager()
    job_id = manager.start(project)

    deadline = time.monotonic() + 5
    child_pid = None
    while time.monotonic() < deadline:
        current = manager.get(job_id)
        if current["output"]:
            try:
                child_pid = int(current["output"][0])
                break
            except ValueError:
                pass
        time.sleep(0.02)

    assert child_pid is not None, "child process did not report its PID"
    assert manager.cancel(job_id) is True
    job = wait_for_terminal(manager, job_id)

    assert job["status"] == "cancelled"
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline and _process_is_running(child_pid):
        time.sleep(0.05)
    assert not _process_is_running(child_pid), "child process survived scan cancellation"
