"""A transparent, deliberately stylized noise model for local challenge warm-up."""

from __future__ import annotations

from qiskit import QuantumCircuit
from qiskit.quantum_info import Operator
from qiskit_aer import AerSimulator
from qiskit_aer.noise import (
    NoiseModel,
    ReadoutError,
    coherent_unitary_error,
    depolarizing_error,
)


def known_noise_model(
    rxx_overrotation: float = 0.2,
    one_qubit_depolarizing: float = 0.001,
) -> NoiseModel:
    """Return the disclosed warm-up model.

    Every physical ``rxx(theta)`` is followed by ``rxx(rxx_overrotation)``.
    Because RXX rotations share a generator, this implements a known additive
    entangling-angle offset: theta -> theta + rxx_overrotation. Participants
    can explicitly investigate compensating it with theta -> theta - offset.
    ``rz`` is omitted because it is virtual/free in the challenge interface.
    """
    if not 0 <= one_qubit_depolarizing <= 1:
        raise ValueError("one_qubit_depolarizing must be between 0 and 1.")

    model = NoiseModel(basis_gates=["rx", "ry", "rz", "rxx"])
    if one_qubit_depolarizing:
        model.add_all_qubit_quantum_error(
            depolarizing_error(one_qubit_depolarizing, 1), ["rx", "ry"]
        )

    coherent_error_circuit = QuantumCircuit(2)
    coherent_error_circuit.rxx(rxx_overrotation, 0, 1)
    model.add_all_qubit_quantum_error(
        coherent_unitary_error(Operator(coherent_error_circuit).data), "rxx"
    )

    # Deliberately asymmetric readout: 1 -> 0 is more likely than 0 -> 1.
    model.add_all_qubit_readout_error(ReadoutError([[0.985, 0.015], [0.040, 0.960]]))
    return model


def run_with_final_measurements(circuit, shots: int = 256, seed: int | None = 7, **noise_parameters):
    """Run a measurement-free candidate under the known model and return counts."""
    measured = circuit.copy()
    measured.measure_all()
    backend = AerSimulator(noise_model=known_noise_model(**noise_parameters), seed_simulator=seed)
    return backend.run(measured, shots=shots).result().get_counts()


def known_noise_truth_table(circuit, shots: int = 1024, seed: int | None = 7, **noise_parameters):
    """Estimate an eight-input truth table under the known model.

    On hardware each row is its own submission: the lab starts from ``|000>``,
    so the input c1c2t is prepared on q[2]q[1]q[0] with native ``rx(pi)`` flips
    (``with_input_preparation``), which the model treats as noisy like any other
    gate. Returns the same ``TruthTableReport`` as ``truth_table_from_bitstrings``.
    """
    from .benchmarking import TOFFOLI_INPUTS, truth_table_from_bitstrings, with_input_preparation

    backend = AerSimulator(noise_model=known_noise_model(**noise_parameters), seed_simulator=seed)
    result_lists = {}
    for input_bits in TOFFOLI_INPUTS:
        prepared = with_input_preparation(circuit, input_bits)
        prepared.measure_all()
        result = backend.run(prepared, shots=shots, memory=True).result()
        result_lists[input_bits] = result.get_memory(prepared)
    return truth_table_from_bitstrings(result_lists)
