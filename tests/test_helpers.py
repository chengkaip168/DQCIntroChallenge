"""Smoke tests for the participant helpers."""

import math

import pytest
from qiskit import QuantumCircuit, QuantumRegister, qasm2

from toffoli_challenge import (
    TOFFOLI_INPUTS,
    baseline_native_toffoli,
    compare_to_toffoli,
    RELAY_URL,
    configure_relay,
    connect_team,
    expected_output_bitstring,
    load_submission_qasm,
    parse_result_filename,
    result_queue_ids,
    results_by_queue_id,
    truth_table_row,
    truth_table_from_bitstrings,
    truth_table_from_results,
    validate_submission_circuit,
    with_input_preparation,
)
from toffoli_challenge.known_noise import known_noise_truth_table


def _truth_table_files(first_queue_id, shots=64, team="team_alpha", outcomes=None):
    """One result file per submission; queue first_queue_id + k prepared input k."""
    return {
        f"{first_queue_id + k}_{shots}_{team}.txt": str([outcomes or expected_output_bitstring(bits)] * shots)
        for k, bits in enumerate(TOFFOLI_INPUTS)
    }


def test_truth_table_targets():
    assert expected_output_bitstring("110") == "111"
    assert expected_output_bitstring("111") == "110"
    assert expected_output_bitstring("101") == "101"


def test_baseline_is_valid_exact_toffoli():
    baseline = baseline_native_toffoli()
    assert validate_submission_circuit(baseline)
    max_error, process_fidelity, _ = compare_to_toffoli(baseline)
    assert max_error < 1e-9
    assert process_fidelity == pytest.approx(1.0)


def test_validator_rejections():
    high_level = QuantumCircuit(3)
    high_level.ccx(2, 1, 0)
    with pytest.raises(ValueError, match="forbidden instruction: ccx"):
        validate_submission_circuit(high_level)

    measured = QuantumCircuit(3)
    measured.measure_all()
    with pytest.raises(ValueError):
        validate_submission_circuit(measured)

    not_finite = QuantumCircuit(3)
    not_finite.rx(math.nan, 0)
    with pytest.raises(ValueError, match="non-finite"):
        validate_submission_circuit(not_finite)

    renamed = QuantumCircuit(QuantumRegister(2, "ctrl"), QuantumRegister(1, "t"))
    with pytest.raises(ValueError, match="single quantum register"):
        validate_submission_circuit(renamed)


def test_exported_qasm_uses_q3_register():
    circuit = QuantumCircuit(3)
    circuit.rxx(0.5, 2, 1)
    circuit.ry(0.3, 0)
    validate_submission_circuit(circuit)
    assert "qreg q[3];" in qasm2.dumps(circuit)

    with_r = QuantumCircuit(3)
    with_r.r(0.3, 0.2, 0)
    with pytest.raises(ValueError, match="forbidden instruction: r"):
        validate_submission_circuit(with_r)


def test_qasm_roundtrip(tmp_path):
    circuit = QuantumCircuit(3)
    circuit.rxx(0.5, 2, 1)
    circuit.rx(0.3, 0)
    circuit.rz(0.2, 1)
    path = tmp_path / "circuit.qasm"
    path.write_text(qasm2.dumps(circuit))
    loaded = load_submission_qasm(path)
    assert dict(loaded.count_ops()) == {"rxx": 1, "rx": 1, "rz": 1}


def test_scoring():
    single = truth_table_row("110", ["111"] * 60 + ["110"] * 4)
    assert single.success_probability == pytest.approx(0.9375)
    perfect = {bits: [expected_output_bitstring(bits)] * 8 for bits in TOFFOLI_INPUTS}
    assert truth_table_from_bitstrings(perfect).mean_success_probability == 1.0


def test_truth_table_from_one_file_per_submission():
    files = {**_truth_table_files(3), **_truth_table_files(20, outcomes="000")}
    assert result_queue_ids(files) == list(range(3, 11)) + list(range(20, 28))
    good = {bits: 3 + k for k, bits in enumerate(TOFFOLI_INPUTS)}
    assert truth_table_from_results(files, good).mean_success_probability == 1.0
    assert truth_table_from_results(files, {bits: 20 + k for k, bits in enumerate(TOFFOLI_INPUTS)}).mean_success_probability == 0.125
    with pytest.raises(ValueError, match="No result files yet"):
        truth_table_from_results(files, {**good, "111": 99})


def test_results_check_shot_count():
    files = _truth_table_files(5)
    first = next(iter(files))
    files[first] = str(["000"] * 3)
    with pytest.raises(ValueError, match="expected 64"):
        results_by_queue_id(files)


def test_parse_result_filename():
    fields = parse_result_filename("17_512_team_alpha.txt")
    assert fields == {"queue_id": 17, "shots": 512, "team_id": "team_alpha"}
    with pytest.raises(ValueError):
        parse_result_filename("17_512_team_alpha_input-110_20261022T153012Z.txt")


def test_input_preparation_is_native_and_correct():
    from qiskit.quantum_info import Statevector

    baseline = baseline_native_toffoli()
    for bits in TOFFOLI_INPUTS:
        prepared = with_input_preparation(baseline, bits)
        validate_submission_circuit(prepared)
        probabilities = Statevector(prepared).probabilities_dict()
        assert probabilities[expected_output_bitstring(bits)] == pytest.approx(1.0)


def test_configure_relay_rejects_bad_team_id():
    with pytest.raises(ValueError, match="TEAM_ID"):
        configure_relay("https://script.google.com/macros/s/x/exec", "Team Alpha", "secret")


def test_packaged_relay_url():
    assert RELAY_URL.startswith("https://script.google.com/macros/s/") and RELAY_URL.endswith("/exec")
    with pytest.raises(ValueError, match="TEAM_ID"):
        connect_team("Team Alpha", "secret")


def test_known_noise_compensation_helps():
    baseline = baseline_native_toffoli()
    compensated = baseline.copy_empty_like()
    for instruction in baseline.data:
        if instruction.operation.name == "rxx":
            compensated.rxx(float(instruction.operation.params[0]) - 0.2, *instruction.qubits)
        else:
            compensated.append(instruction)
    raw = known_noise_truth_table(baseline, shots=1024, seed=11).mean_success_probability
    fixed = known_noise_truth_table(compensated, shots=1024, seed=11).mean_success_probability
    assert fixed > raw


def test_ionq_helpers_offline(tmp_path):
    from toffoli_challenge.ionq import (
        counts_to_bitstrings,
        load_job_log,
        record_job,
        truth_table_circuits,
        truth_table_from_counts,
    )

    circuits = truth_table_circuits(baseline_native_toffoli())
    assert [c.name for c in circuits] == [f"input-{bits}" for bits in TOFFOLI_INPUTS]
    assert all(c.num_clbits == 3 for c in circuits)
    assert counts_to_bitstrings({"110": 2, "1 1 1": 1}) == ["110", "110", "111"]
    assert counts_to_bitstrings({"11": 1, "0x6": 1}) == ["011", "110"]
    with pytest.raises(ValueError):
        counts_to_bitstrings({"0110": 1})
    perfect = {bits: {expected_output_bitstring(bits): 64} for bits in TOFFOLI_INPUTS}
    assert truth_table_from_counts(perfect).mean_success_probability == 1.0

    class FakeJob:
        def job_id(self):
            return "abc-123"

    log = tmp_path / "jobs.json"
    record_job(FakeJob(), "ionq_simulator", "truth table", 64, path=log, noise_model="forte-1")
    assert load_job_log(log)[0]["job_id"] == "abc-123"
    assert load_job_log(tmp_path / "missing.json") == []
