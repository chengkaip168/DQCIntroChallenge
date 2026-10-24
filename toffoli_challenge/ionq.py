"""Helpers for the IonQ extension (midnight to noon, on IonQ Forte 1).

Nothing here talks to IonQ on its own and nothing imports ``qiskit_ionq``: the
notebook creates the backend with the participant's own API key and passes it
in. Install the extra package with ``python -m pip install -r requirements-ionq.txt``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from .benchmarking import (
    TOFFOLI_INPUTS,
    TruthTableReport,
    truth_table_from_bitstrings,
    with_input_preparation,
)
from .validation import validate_submission_circuit

DEFAULT_JOB_LOG = "ionq_jobs.json"

# The event uses one machine, IonQ Forte 1, and its matching simulator noise model.
IONQ_QPU = "qpu.forte-1"
IONQ_NOISE_MODEL = "forte-1"
IONQ_SIMULATOR = "ionq_simulator"


def measured_copy(candidate, name: str | None = None):
    """Validate a submission-style circuit and return a copy with final measurements.

    IonQ backends need explicit measurements; the hardware queue added them for
    you. The circuit itself must still obey the challenge rules.
    """
    validate_submission_circuit(candidate)
    circuit = candidate.copy(name=name or candidate.name)
    circuit.measure_all()
    return circuit


def truth_table_circuits(candidate) -> list:
    """Return the eight measured input-prepared circuits, in ``TOFFOLI_INPUTS`` order."""
    return [
        measured_copy(with_input_preparation(candidate, input_bits), name=f"input-{input_bits}")
        for input_bits in TOFFOLI_INPUTS
    ]


def counts_to_bitstrings(counts: Mapping[str, int]) -> list[str]:
    """Expand a counts dictionary into the raw ``q[2]q[1]q[0]`` list the truth-table helpers expect."""
    bitstrings = []
    for key, count in counts.items():
        bits = str(key).replace(" ", "")
        if bits.startswith("0x"):
            bits = format(int(bits, 16), "b")
        # Leading zeros can be dropped when a result header is missing; keys are MSB-left.
        bits = bits.zfill(3)
        if len(bits) != 3 or set(bits) - {"0", "1"}:
            raise ValueError(f"Expected three-bit outcomes such as '110'; got {key!r}.")
        bitstrings.extend([bits] * int(count))
    if not bitstrings:
        raise ValueError("The counts dictionary is empty.")
    return bitstrings


def truth_table_from_counts(counts_by_input: Mapping[str, Mapping[str, int]]) -> TruthTableReport:
    """Build a truth table from ``{'000': counts, ..., '111': counts}`` exactly like a hardware truth table."""
    return truth_table_from_bitstrings(
        {input_bits: counts_to_bitstrings(counts) for input_bits, counts in counts_by_input.items()}
    )


def truth_table_from_job(job) -> TruthTableReport:
    """Build the truth table of a finished job that ran ``truth_table_circuits(...)`` as one batch."""
    result = job.result()  # waits until the job has finished
    return truth_table_from_counts(
        {input_bits: result.get_counts(index) for index, input_bits in enumerate(TOFFOLI_INPUTS)}
    )


def gate_counts(circuit) -> tuple[int, int]:
    """Return ``(one_qubit_gates, two_qubit_gates)`` of a circuit, ignoring measurements and barriers."""
    oneq = twoq = 0
    for instruction in circuit.data:
        name = instruction.operation.name
        if name in ("measure", "barrier"):
            continue
        if len(instruction.qubits) == 1:
            oneq += 1
        else:
            twoq += 1
    return oneq, twoq


def estimate_cost(backend, circuit, shots: int) -> dict:
    """Ask IonQ what one circuit would cost on ``backend``, with debiasing off.

    Returns IonQ's raw estimate, which includes your organization's rate card
    (cost per 1q gate, per 2q gate and the minimum per circuit). Nothing runs and
    nothing is charged. A multi-circuit job costs the sum of its circuits.
    IonQ bills the circuit after its own compilation, so treat this as a guide.
    """
    client = backend.client
    oneq, twoq = gate_counts(circuit)
    response = client.get_with_retry(
        client.make_path("jobs", "estimate"),
        headers=client.api_headers,
        params={
            "backend": backend.name.replace("ionq_qpu", "qpu"),
            "qubits": circuit.num_qubits,
            "shots": int(shots),
            "1q_gates": oneq,
            "2q_gates": twoq,
            "error_mitigation": "false",
        },
    )
    response.raise_for_status()
    return response.json()


def run_without_debiasing(backend, circuits, shots: int, **options):
    """Submit to IonQ with debiasing (IonQ's built-in error mitigation) switched off.

    Debiasing is not allowed in this challenge, so every QPU job goes through here.
    """
    from qiskit_ionq import ErrorMitigation

    if "error_mitigation" in options:
        raise ValueError("Debiasing is not allowed in this challenge; error_mitigation is always off.")
    return backend.run(circuits, shots=int(shots), error_mitigation=ErrorMitigation.NO_DEBIASING, **options)


def record_job(job, backend_name: str, label: str, shots: int, path: str | Path = DEFAULT_JOB_LOG, **details) -> dict:
    """Append a submitted job to a local JSON log so it survives a kernel restart."""
    entry = {
        "job_id": job.job_id(),
        "label": label,
        "backend": backend_name,
        "shots": shots,
        "submitted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        **details,
    }
    log = load_job_log(path)
    log.append(entry)
    Path(path).write_text(json.dumps(log, indent=2), encoding="utf-8")
    return entry


def load_job_log(path: str | Path = DEFAULT_JOB_LOG) -> list[dict]:
    """Return every job recorded by ``record_job`` (an empty list if there are none)."""
    path = Path(path)
    if not path.is_file():
        return []
    return json.loads(path.read_text(encoding="utf-8"))
