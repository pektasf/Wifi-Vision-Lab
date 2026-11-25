# Structured scan events

The command-line scan runner and the Streamlit background job manager exchange
progress through stdout. This keeps the scan pipeline independent from the UI
and avoids parsing user-facing Turkish log messages.

## Wire format

Each event is one UTF-8 JSON object on one line, preceded by the literal
`WIFI_VISION_EVENT ` prefix:

```json
{
  "type": "progress",
  "stage": "Ağ topolojisi",
  "progress": 0.72,
  "message": "Topoloji ilişkileri hesaplanıyor"
}
```

- `type` is currently `progress`.
- `stage` is a short stage label.
- `progress` is a number clamped to the inclusive range 0–1.
- `message` is a short optional status message.
- Unknown, malformed, or unrelated stdout lines are ignored by the event
  parser and remain visible in the captured job output.

## Ownership

- `scripts/scan_events.py` owns event formatting and parsing.
- `main.py` emits stage-level progress while orchestrating modules.
- `scripts/scan_jobs.py` consumes events and exposes a UI-neutral job snapshot.
- Streamlit renders the snapshot; it does not own scan execution.

The protocol is intentionally small and local-only. It does not send telemetry
or network observations outside the machine. Collectors can later emit more
detailed events without changing the UI contract.
