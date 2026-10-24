"""Truth-table and ideal-unitary helpers for the Toffoli challenge.

These functions make local development and result inspection reproducible. They
produce evidence, not a verdict: there is no leaderboard, and what a truth table
does and does not show is part of the argument each team makes.
"""

from __future__ import annotations

import ast
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

import numpy as np


TOFFOLI_INPUTS = tuple(f"{value:03b}" for value in range(8))
_BITSTRING_RE = re.compile(r"[01]{3}")
_RESULT_FILENAME_RE = re.compile(
    r"^(?P<queue_id>\d+)_(?P<shots>64|128|256|512|1024)_"
    r"(?P<team_id>[a-z0-9][a-z0-9_-]{0,31})\.txt$"
)


@dataclass(frozen=True)
class InputTruthTableResult:
    """The observed success probability for one prepared computational input."""

    input_bits: str
    ideal_output: str
    shots: int
    successes: int
    success_probability: float
    counts: dict[str, int]


@dataclass(frozen=True)
class TruthTableReport:
    """Equal-weight eight-input computational-basis success rate."""

    mean_success_probability: float
    per_input: dict[str, InputTruthTableResult]


def expected_output_bitstring(input_bits: str) -> str:
    """Return CCX(2, 1, 0)'s output in the ``q[2]q[1]q[0] = c1c2t`` order."""
    if not isinstance(input_bits, str) or not _BITSTRING_RE.fullmatch(input_bits):
        raise ValueError("Input must be a three-character c1c2t string, e.g. '110'.")
    c1, c2, target = (int(bit) for bit in input_bits)
    return f"{c1}{c2}{target ^ (c1 & c2)}"


def normalize_bitstring_list(raw_bitstrings: str | Iterable[str]) -> list[str]:
    """Parse and validate a bare lab result list; never use ``eval`` on results."""
    if isinstance(raw_bitstrings, str):
        text = raw_bitstrings.strip()
        try:
            raw_bitstrings = ast.literal_eval(text)
        except (SyntaxError, ValueError):
            raw_bitstrings = [line.strip() for line in text.splitlines() if line.strip()]
    try:
        values = list(raw_bitstrings)
    except TypeError as error:
        raise ValueError("Expected a bitstring list or text containing one.") from error
    if not values:
        raise ValueError("The hardware result list is empty.")
    if any(not isinstance(value, str) or not _BITSTRING_RE.fullmatch(value) for value in values):
        raise ValueError("Every hardware outcome must be a three-bit string, such as '111'.")
    return values


def load_bitstring_list(path: str | Path) -> list[str]:
    """Read a raw list of bitstrings from a text file, with no JSON expected."""
    return normalize_bitstring_list(Path(path).read_text(encoding="utf-8"))


def bitstrings_to_counts(raw_bitstrings: str | Iterable[str]) -> dict[str, int]:
    """Convert a laboratory bitstring list to an ordinary counts dictionary."""
    return dict(Counter(normalize_bitstring_list(raw_bitstrings)))


def truth_table_row(
    input_bits: str, raw_bitstrings: str | Iterable[str]
) -> InputTruthTableResult:
    """Compare one Z-basis output list with its ideal Toffoli output."""
    values = normalize_bitstring_list(raw_bitstrings)
    ideal = expected_output_bitstring(input_bits)
    counts = dict(Counter(values))
    successes = counts.get(ideal, 0)
    return InputTruthTableResult(
        input_bits=input_bits,
        ideal_output=ideal,
        shots=len(values),
        successes=successes,
        success_probability=successes / len(values),
        counts=counts,
    )


def truth_table_from_bitstrings(
    result_lists: Mapping[str, str | Iterable[str]]
) -> TruthTableReport:
    """Combine all eight computational inputs with equal weight.

    ``result_lists`` is assembled locally as ``{'000': raw_000, ..., '111': raw_111}``,
    typically one submission per input (see ``truth_table_from_results``). It is
    intentionally not a new laboratory result format: every individual
    laboratory file remains only a raw list of bitstrings.
    """
    if set(result_lists) != set(TOFFOLI_INPUTS):
        raise ValueError("Provide exactly eight raw lists keyed by inputs 000 through 111.")
    per_input = {
        input_bits: truth_table_row(input_bits, result_lists[input_bits])
        for input_bits in TOFFOLI_INPUTS
    }
    return TruthTableReport(
        mean_success_probability=float(np.mean([entry.success_probability for entry in per_input.values()])),
        per_input=per_input,
    )


def parse_result_filename(filename: str) -> dict[str, str | int]:
    """Split a flat result filename into queue ID, shots, and team ID."""
    match = _RESULT_FILENAME_RE.fullmatch(Path(filename).name)
    if not match:
        raise ValueError(
            f"Not a valid challenge result filename: {filename!r} "
            "(expected <queueID>_<shots>_<teamID>.txt)"
        )
    fields = match.groupdict()
    fields["queue_id"] = int(fields["queue_id"])
    fields["shots"] = int(fields["shots"])
    return fields


def result_queue_ids(raw_text_by_filename: Mapping[str, str]) -> list[int]:
    """Return the sorted queue IDs present in relay-returned result files."""
    return sorted({parse_result_filename(name)["queue_id"] for name in raw_text_by_filename})


def results_by_queue_id(raw_text_by_filename: Mapping[str, str]) -> dict[int, list[str]]:
    """Parse relay-returned result files into ``{queue_id: bitstring list}``.

    The lab runs each submission once, exactly as submitted, and returns one
    file per submission. Each list must hold the shot count named in its filename.
    """
    parsed: dict[int, list[str]] = {}
    for filename, text in raw_text_by_filename.items():
        fields = parse_result_filename(filename)
        if fields["queue_id"] in parsed:
            raise ValueError(f"More than one result file was returned for queue ID {fields['queue_id']}.")
        values = normalize_bitstring_list(text)
        if len(values) != fields["shots"]:
            raise ValueError(
                f"{Path(filename).name} contains {len(values)} outcomes, expected {fields['shots']}."
            )
        parsed[fields["queue_id"]] = values
    return dict(sorted(parsed.items()))


def truth_table_from_results(
    raw_text_by_filename: Mapping[str, str], queue_id_by_input: Mapping[str, int]
) -> TruthTableReport:
    """Build a truth table from eight submissions, one per prepared input.

    ``queue_id_by_input`` maps each input to the queue ID of the submission that
    prepared it, e.g. ``{'000': 17, '001': 18, ..., '111': 24}``.
    """
    by_queue = results_by_queue_id(raw_text_by_filename)
    missing = sorted(q for q in queue_id_by_input.values() if q not in by_queue)
    if missing:
        raise ValueError(f"No result files yet for queue IDs {missing}; available: {list(by_queue)}.")
    return truth_table_from_bitstrings(
        {input_bits: by_queue[queue_id] for input_bits, queue_id in queue_id_by_input.items()}
    )


def with_input_preparation(circuit, input_bits: str):
    """Return ``circuit`` preceded by native ``rx(pi)`` flips that prepare ``input_bits``.

    The lab always starts from ``|000>``, so a truth-table row is a separate
    submission of this prepared circuit. ``input_bits`` is in ``c1c2t`` order,
    i.e. ``q[2]q[1]q[0]``. ``rx(pi)`` equals X up to a global phase.
    """
    if not isinstance(input_bits, str) or not _BITSTRING_RE.fullmatch(input_bits):
        raise ValueError("Input must be a three-character c1c2t string, e.g. '110'.")
    prepared = circuit.copy_empty_like()
    for qubit, bit in enumerate(reversed(input_bits)):
        if bit == "1":
            prepared.rx(np.pi, qubit)
    prepared.compose(circuit, inplace=True)
    return prepared


def ideal_toffoli_in_submission_order():
    """Construct the high-level CCX reference with controls q[2], q[1], target q[0]."""
    from qiskit import QuantumCircuit

    target = QuantumCircuit(3)
    target.ccx(2, 1, 0)
    return target


def baseline_native_toffoli():
    """Return Qiskit's automatic native-gate compilation of the reference Toffoli.

    This is a valid starting submission (five ``rxx`` gates), not an optimized
    one. The challenge is to beat it.
    """
    from qiskit import transpile

    return transpile(
        ideal_toffoli_in_submission_order(),
        basis_gates=["rx", "ry", "rz", "rxx"],
        optimization_level=3,
        seed_transpiler=1,
    )


def compare_to_toffoli(candidate) -> tuple[float, float, float]:
    """Return max matrix error, process fidelity, and average gate fidelity ideally."""
    from qiskit.quantum_info import Operator

    candidate_matrix = Operator(candidate).data
    target_matrix = Operator(ideal_toffoli_in_submission_order()).data
    overlap = np.trace(target_matrix.conj().T @ candidate_matrix)
    phase = overlap / abs(overlap) if abs(overlap) > 1e-14 else 1.0
    max_abs_error = float(np.max(np.abs(candidate_matrix - phase * target_matrix)))
    process_fidelity = float(abs(overlap / 8) ** 2)
    average_gate_fidelity = float((8 * process_fidelity + 1) / 9)
    return max_abs_error, process_fidelity, average_gate_fidelity
