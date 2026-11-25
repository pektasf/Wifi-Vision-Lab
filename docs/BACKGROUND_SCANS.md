# Background scan jobs

The Streamlit UI starts the existing `main.py` scan entry point in a
background worker. The UI request returns immediately; the scan process
continues while the Streamlit server remains running.

## Job lifecycle

- States: `queued`, `running`, `completed`, `failed`, `cancelled`.
- The worker captures combined stdout/stderr and retains only the latest
  2,000 lines in memory.
- The sidebar refreshes job status once per second and offers cancellation.
- Progress is derived from the existing discovery stage and target-count output.
- Cancellation terminates the scan subprocess. A cancelled scan may have
  already written partial output files; existing collectors are not yet
  transactional as a whole.
- Job state and captured output are in memory only. Restarting Streamlit
  discards job history; network observations continue to use existing local
  CSV storage.

## Safety and scope

The worker invokes Python with an argument list (no shell) and inherits the
existing scan policy. Custom CIDR still requires authorization and exact
confirmation before the child process is started. This feature does not
change host, worker, or timeout limits and does not run a scan in CI.

## Current limitations

This is a single-process job manager, not a distributed queue. It enforces
one active scan at a time because collectors share local CSV files.
Progress is inferred from the existing discovery console messages. Other
analysis modules do not yet report structured progress, and cancellation
terminates the scan process rather than stopping each collector cooperatively.
