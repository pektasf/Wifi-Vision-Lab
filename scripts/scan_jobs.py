"""In-process background job manager for local discovery scans.

Jobs are intentionally ephemeral: status/output live only for the lifetime of
the Streamlit server process. Network observations remain in existing storage.
"""
from __future__ import annotations

import os
import re
import signal
import subprocess
import sys
import threading
import time
import uuid
from collections import deque
from pathlib import Path
from typing import Any

from scripts.scan_events import parse_event_line


class ScanJobManager:
    def __init__(self, output_limit: int = 2000):
        self._lock = threading.RLock()
        self._jobs: dict[str, dict[str, Any]] = {}
        self._processes: dict[str, subprocess.Popen[str]] = {}
        self._output_limit = max(100, int(output_limit))

    def start(
        self,
        project_root: str | Path,
        *,
        scan_cidr: str = "",
        approved: bool = False,
        confirmation: str = "",
        interface_alias: str = "",
    ) -> str:
        """Start main.py in a worker thread and return its job identifier."""
        if scan_cidr and (not approved or confirmation != scan_cidr):
            raise ValueError("Custom CIDR requires authorization and exact confirmation.")

        root = Path(project_root).resolve()
        main_file = root / "main.py"
        if not main_file.is_file():
            raise FileNotFoundError(f"Scan entry point not found: {main_file}")

        env = os.environ.copy()
        for key in (
            "WIFI_VISION_SCAN_CIDR",
            "WIFI_VISION_SCAN_APPROVED",
            "WIFI_VISION_SCAN_CONFIRMATION",
            "WIFI_VISION_INTERFACE_ALIAS",
        ):
            env.pop(key, None)
        if scan_cidr:
            env["WIFI_VISION_SCAN_CIDR"] = scan_cidr
            env["WIFI_VISION_SCAN_APPROVED"] = "1"
            env["WIFI_VISION_SCAN_CONFIRMATION"] = confirmation
        if interface_alias:
            env["WIFI_VISION_INTERFACE_ALIAS"] = str(interface_alias).strip()

        job_id = uuid.uuid4().hex
        job = {
            "job_id": job_id,
            "status": "queued",
            "started_at": None,
            "finished_at": None,
            "return_code": None,
            "output": deque(maxlen=self._output_limit),
            "error": "",
            "cancel_requested": False,
            "progress": 0.0,
            "stage": "Sırada",
            "progress_message": "",
            "completed_targets": 0,
            "total_targets": 0,
        }
        with self._lock:
            active = [
                item for item in self._jobs.values()
                if item["status"] in {"queued", "running"}
            ]
            if active:
                raise RuntimeError("A scan is already active. Wait for it to finish or cancel it.")
            self._jobs[job_id] = job
        worker = threading.Thread(
            target=self._run,
            args=(job_id, root, env),
            name=f"wifi-scan-{job_id[:8]}",
            daemon=True,
        )
        worker.start()
        return job_id

    def _run(self, job_id: str, root: Path, env: dict[str, str]) -> None:
        process = None
        with self._lock:
            job = self._jobs[job_id]
            job["status"] = "running"
            job["started_at"] = time.time()
        try:
            process = subprocess.Popen(
                [sys.executable, "-u", str(root / "main.py")],
                cwd=str(root),
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                shell=False,
                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
                start_new_session=(os.name != "nt"),
            )
            with self._lock:
                self._processes[job_id] = process
                cancelled = self._jobs[job_id]["cancel_requested"]
            if cancelled:
                self._terminate_process_tree(process)

            assert process.stdout is not None
            for line in process.stdout:
                clean_line = line.rstrip("\r\n")
                with self._lock:
                    job = self._jobs[job_id]
                    job["output"].append(clean_line)
                    self._update_progress(job, clean_line)
            return_code = process.wait()
            with self._lock:
                job = self._jobs[job_id]
                job["return_code"] = return_code
                if job["cancel_requested"]:
                    job["status"] = "cancelled"
                else:
                    job["status"] = "completed" if return_code == 0 else "failed"
        except Exception as exc:
            with self._lock:
                job = self._jobs[job_id]
                job["status"] = "failed"
                job["error"] = f"{type(exc).__name__}: {exc}"
        finally:
            with self._lock:
                job = self._jobs[job_id]
                job["finished_at"] = time.time()
                self._processes.pop(job_id, None)
            if process is not None and process.stdout is not None:
                process.stdout.close()

    @staticmethod
    def _update_progress(job: dict[str, Any], line: str) -> None:
        """Prefer structured events; retain legacy log parsing for older runners."""
        event = parse_event_line(line)
        if event is not None:
            job["stage"] = event["stage"]
            job["progress"] = max(job["progress"], event["progress"])
            job["progress_message"] = event["message"]
            return

        stage_match = re.search(r"\[(\d+)/4\]", line)
        if stage_match:
            stage_number = int(stage_match.group(1))
            stage_labels = {
                1: "Ağ algılanıyor",
                2: "Cihazlar taranıyor",
                3: "ARP ve cihaz bilgileri okunuyor",
                4: "Sonuçlar kaydediliyor",
            }
            job["stage"] = stage_labels.get(stage_number, "Çalışıyor")
            job["progress"] = max(job["progress"], (stage_number - 1) / 4)

        target_match = re.search(r"Tarama:\s*(\d+)/(\d+)", line)
        if target_match:
            completed = int(target_match.group(1))
            total = max(1, int(target_match.group(2)))
            job["completed_targets"] = completed
            job["total_targets"] = total
            job["stage"] = "Cihazlar taranıyor"
            job["progress"] = max(
                job["progress"],
                0.25 + 0.60 * min(1.0, completed / total),
            )

        if "Tarama tamamlandi." in line or "Scan complete:" in line:
            job["stage"] = "Tamamlandı"
            job["progress"] = 1.0

    def cancel(self, job_id: str) -> bool:
        """Request cancellation. Returns False when the job is already terminal."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job["status"] in {"completed", "failed", "cancelled"}:
                return False
            job["cancel_requested"] = True
            process = self._processes.get(job_id)
            if process is None:
                return True
        if process is not None:
            self._terminate_process_tree(process)
        return True

    @staticmethod
    def _terminate_process_tree(process: subprocess.Popen[str]) -> None:
        """Stop the scan process and descendants, not only the Python parent."""
        if process.poll() is not None:
            return

        if os.name == "nt":
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=10,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired):
                pass
        else:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass

        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            return {
                "job_id": job["job_id"],
                "status": job["status"],
                "started_at": job["started_at"],
                "finished_at": job["finished_at"],
                "return_code": job["return_code"],
                "output": list(job["output"]),
                "error": job["error"],
                "cancel_requested": job["cancel_requested"],
                "progress": job["progress"],
                "stage": job["stage"],
                "progress_message": job["progress_message"],
                "completed_targets": job["completed_targets"],
                "total_targets": job["total_targets"],
            }


scan_jobs = ScanJobManager()
