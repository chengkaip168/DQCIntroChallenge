"""Small, credential-free client for the organizer-operated submission relay."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from qiskit import qasm2

from .validation import STANDARD_SHOTS, validate_submission_circuit


@dataclass(frozen=True)
class RelayConfiguration:
    url: str
    team_id: str
    team_secret: str


# The organizer-operated relay for this event. It is public: the relay trusts a
# request only if it carries a valid TEAM_ID and TEAM_SECRET.
RELAY_URL = (
    "https://script.google.com/macros/s/"
    "AKfycbx39_vpA6MSeXE4ZO85mtpt8wvEFvkvtwDDBjU9ALeHdqx7VodkSeM1BJ7XPy-5tCS5/exec"
)

_config: RelayConfiguration | None = None
# Must match authenticateTeam_ in the relay and the result-filename contract.
_TEAM_ID_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,31}")


def configure_relay(relay_url: str, team_id: str, team_secret: str) -> None:
    """Configure this session for any relay deployment; credentials stay in memory.

    Participants use ``connect_team``; organizers use this to test a deployment.
    """
    if not relay_url.rstrip().endswith("/exec"):
        raise ValueError("RELAY_URL must be the deployed Apps Script URL ending in /exec.")
    if not team_id or not team_secret:
        raise ValueError("Both TEAM_ID and TEAM_SECRET are required.")
    if not _TEAM_ID_RE.fullmatch(team_id.strip()):
        raise ValueError(
            "TEAM_ID must be the organizer-issued ID: lowercase letters, digits, _ or -, "
            "at most 32 characters (e.g. 'quantum_cats')."
        )
    global _config
    _config = RelayConfiguration(relay_url.strip(), team_id.strip(), team_secret.strip())


def connect_team(team_id: str, team_secret: str) -> None:
    """Configure this session for the event relay with your organizer-issued credentials."""
    configure_relay(RELAY_URL, team_id, team_secret)


def _require_config() -> RelayConfiguration:
    if _config is None:
        raise RuntimeError("Call connect_team(TEAM_ID, TEAM_SECRET) first.")
    return _config


def _post(payload: dict) -> dict:
    config = _require_config()
    body = {"team_id": config.team_id, "team_secret": config.team_secret, **payload}
    request = Request(
        config.url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as error:
        raise RuntimeError(f"Relay HTTP {error.code}: {error.read().decode('utf-8', 'replace')}") from error
    except URLError as error:
        raise RuntimeError(f"Could not reach the submission relay: {error.reason}") from error
    try:
        reply = json.loads(raw)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"Relay returned non-JSON content: {raw[:300]!r}") from error
    if not reply.get("ok"):
        raise RuntimeError(reply.get("error", "Relay request failed."))
    return reply


def submit_qasm_text(qasm_text: str, shots: int) -> dict:
    """Submit an in-memory OpenQASM 2 program; the relay assigns the queue ID."""
    if shots not in STANDARD_SHOTS:
        raise ValueError(f"Choose one of {sorted(STANDARD_SHOTS)} shots.")
    if not isinstance(qasm_text, str):
        raise TypeError("qasm_text must be a string.")
    return _post({"action": "submit", "shots": shots, "qasm": qasm_text})


def submit_circuit(circuit, shots: int) -> dict:
    """Validate, serialize, and submit a Qiskit QuantumCircuit without writing a file."""
    validate_submission_circuit(circuit)
    return submit_qasm_text(qasm2.dumps(circuit), shots)


def remaining_hardware_shots() -> dict:
    """Return this team's charged and remaining hardware-shot totals."""
    return _post({"action": "submission_status"})


def fetch_my_results(
    destination: str | Path | None = "returned_results", queue_id: int | None = None
) -> dict[str, str]:
    """Fetch this team's raw bitstring-list results from the relay.

    Each submission yields one result file, ``<queueID>_<shots>_<teamID>.txt``.
    Pass ``queue_id`` (from a submission receipt) to fetch only that submission's
    file; otherwise every file returned to your team so far is fetched.
    """
    payload = {"action": "get_results"}
    if queue_id is not None:
        payload["queue_id"] = int(queue_id)
    reply = _post(payload)
    result_lists = {}
    output_dir = Path(destination) if destination is not None else None
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
    for result in reply["results"]:
        filename = Path(result["filename"]).name
        if queue_id is not None and not filename.startswith(f"{int(queue_id)}_"):
            continue
        raw_text = result["content"]
        if output_dir is not None:
            (output_dir / filename).write_text(raw_text, encoding="utf-8")
        result_lists[filename] = raw_text
    return result_lists
