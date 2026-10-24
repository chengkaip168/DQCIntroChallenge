"""Submission-interface checks shared by the notebook and relay client."""

from __future__ import annotations

import cmath

STANDARD_SHOTS = {64, 128, 256, 512, 1024}
NATIVE_GATES = {"rx", "ry", "rz", "rxx"}


def validate_submission_circuit(circuit) -> bool:
    """Raise ValueError unless a Qiskit circuit obeys the challenge interface."""
    problems = []
    if circuit.num_qubits != 3:
        problems.append(f"exactly 3 qubits required; found {circuit.num_qubits}")
    if circuit.num_clbits != 0:
        problems.append("submitted circuit must have zero classical bits")
    # The relay and lab expect exactly `qreg q[3];` in the exported QASM.
    if [(register.name, register.size) for register in circuit.qregs] != [("q", 3)]:
        problems.append(
            "use a single quantum register named 'q', e.g. QuantumCircuit(3); "
            f"found {[(register.name, register.size) for register in circuit.qregs]}"
        )
    if circuit.parameters:
        problems.append(f"parameterized circuit is not allowed: {circuit.parameters}")

    for instruction in circuit.data:
        operation = instruction.operation
        if operation.name not in NATIVE_GATES:
            problems.append(f"forbidden instruction: {operation.name}")
        for parameter in operation.params:
            try:
                value = complex(parameter)
            except (TypeError, ValueError):
                problems.append(
                    f"non-numeric parameter in {operation.name}: {parameter!r}"
                )
                continue
            if not cmath.isfinite(value):
                problems.append(f"non-finite parameter in {operation.name}: {parameter!r}")

    if problems:
        raise ValueError("Submission validation failed:\n- " + "\n- ".join(problems))
    return True


def load_submission_qasm(path, validate: bool = True):
    """Load a QASM file written by ``qasm2.dumps`` back into a QuantumCircuit.

    Qiskit's default OpenQASM 2 parser rejects the ``rxx`` gate that
    ``qasm2.dumps`` writes; the legacy custom instructions restore it.
    """
    from qiskit import qasm2

    circuit = qasm2.load(path, custom_instructions=qasm2.LEGACY_CUSTOM_INSTRUCTIONS)
    if validate:
        validate_submission_circuit(circuit)
    return circuit
