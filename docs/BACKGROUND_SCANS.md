# Background scan jobs

The Streamlit UI starts the existing `main.py` scan entry point in a
background worker. The UI request returns immediately; the scan process
continues while the Streamlit server remains running.

## Job lifecycle

- States: `queued`, `running`, `completed`, `failed`, `cancelled`.
- The worker captures combined stdout/stderr and retains only the latest
  2,000 lines in memory.
- The sidebar refreshes job status once per second and offers cancellation.
- The scan runner emits structured JSON-lines progress events for each analysis stage.
- Older discovery target-count console lines remain supported as a fallback.
- Cancellation terminates the scan process tree (the Python runner and its
  descendants). A cancelled scan may have already written partial output
  files; existing collectors are not transactional as a whole.
- Job state and captured output are in memory only. Restarting Streamlit
  discards job history; network observations continue to use existing local
  SQLite storage with CSV compatibility exports.

## Safety and scope

The worker invokes Python with an argument list (no shell) and inherits the
existing scan policy. Custom CIDR still requires authorization and exact
confirmation before the child process is started. This feature does not
change host, worker, or timeout limits and does not run a scan in CI.

## Current limitations

This is a single-process job manager, not a distributed queue. It enforces
one active scan at a time because collectors share local CSV files.
The orchestration layer reports stage-level progress through
`scripts/scan_events.py`. Individual collectors do not yet report their own
internal progress, so a long-running stage can remain at the same percentage
until it finishes. Cancellation is OS-level process-tree termination, not cooperative stopping
inside each collector.


## Process-tree cancellation

Each scan runs in its own process group/session. On Windows, cancellation uses
`taskkill /T /F` against the scan PID so child processes are included; on
POSIX systems, the worker sends termination to the process group and escalates
to a kill signal if needed. The worker still waits for the parent process to
exit before marking the job terminal.

This is best-effort OS process cleanup, not cooperative cancellation. A scan
may have already committed partial CSV/SQLite results before cancellation.
