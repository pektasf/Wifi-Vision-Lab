"""In-process background job manager for local discovery scans.

Jobs are intentionally ephemeral: status/output live only for the lifetime of
the Streamlit server process. Network observations remain in existing storage.
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
import uuid
from collections import deque
from pathlib import Path
from typing import Any


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
        ):
            env.pop(key, None)
        if scan_cidr:
            env["WIFI_VISION_SCAN_CIDR"] = scan_cidr
            env["WIFI_VISION_SCAN_APPROVED"] = "1"
            env["WIFI_VISION_SCAN_CONFIRMATION"] = confirmation

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
            )
            with self._lock:
                self._processes[job_id] = process
                cancelled = self._jobs[job_id]["cancel_requested"]
            if cancelled:
                process.terminate()

            assert process.stdout is not None
            for line in process.stdout:
                with self._lock:
                    self._jobs[job_id]["output"].append(line.rstrip("\r\n"))
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
            try:
                process.terminate()
            except ProcessLookupError:
                pass
            return True

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
            }


scan_jobs = ScanJobManager()
