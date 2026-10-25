# Toffoli Hardware Hackathon

This repository is the participant-facing starter kit for the Toffoli challenge.
Fork it, clone your fork, and work in
`notebooks/Toffoli_Hardware_Hackathon_Challenge.ipynb`.
Our team's report for this challenge is in `notebooks/team_toffoli.ipynb`.

**The challenge:** build a Toffoli gate from the native gates `rx`, `ry`, `rz`
and `rxx`, run it on real hardware, and **prove that your Toffoli gate is the
best**. There is no leaderboard and no scoring formula: you decide what "best"
means, gather the evidence, and present the case to the judges (notebook
Section 10). Section 8 of the notebook, on verifying a gate beyond its truth
table, is a good place to start thinking about evidence.

You do **not** need GitLab credentials, an API token, or any knowledge of the
hardware-submission plumbing. The notebook exposes only:

```python
connect_team(TEAM_ID, TEAM_SECRET)
submit_circuit(candidate, shots=512)
remaining_hardware_shots()
fetch_my_results(queue_id=...)
```

Each submission is run once, exactly as written, starting from `|000>`, and
returns one result file of raw bitstrings. Each team has **20,000 hardware
shots** in total.

Hardware submissions are accepted only from **4:00 PM to 12:00 midnight** on
the event day. The relay refuses submissions outside that window; fetching
results works at any time.

## After midnight: the IonQ extension (midnight to noon)

When the hardware queue closes, the challenge continues for 12 more hours on
IonQ's **Forte 1** trapped-ion computer, with the same goal, gates and wire
convention. The organizers release the IonQ notebook at midnight. To be ready:

1. Accept the IonQ invitation email during the evening and sign in to the
   [IonQ Quantum Cloud](https://cloud.ionq.com/) with the invited address.
2. Check that you can see your team's project, `intro-<your team ID>`.
3. Install the IonQ package now, so there is nothing to install at midnight:

   ```bash
   python -m pip install -r requirements-ionq.txt
   ```

   Codespaces does this for you.

The notebook walks you through creating an API key and running on IonQ's free
simulator before any QPU job. IonQ's built-in error mitigation (debiasing) is
not allowed; the helpers switch it off for you.

## Setup

Use Python 3.10 or newer (the kit is tested with Python 3.12, see
`.python-version`). From the root of your clone, ideally inside a fresh virtual
environment:

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
jupyter lab
```

`requirements.txt` pins the exact tested versions of Qiskit, Qiskit Aer and the
other dependencies, and installs this repository as an **editable package**.
The editable install makes `import toffoli_challenge` work whether Jupyter opens
the notebook from the repository root, the `notebooks/` directory, or another
working directory. Restart the notebook kernel after editing any helper module.

The notebook's first code cell checks the environment. If it reports that
`toffoli_challenge` is missing, the kernel is running in a different Python
environment from the one you installed into.

**No local setup?** Open your fork in GitHub Codespaces (**Code → Codespaces →
Create codespace**). The included `.devcontainer` installs the pinned
environment automatically. In Google Colab, run
`!pip install -q "git+https://github.com/<you>/<your-fork>.git"` in
the first cell instead.

The organizer supplies each team with two values, `TEAM_ID` and `TEAM_SECRET`.
Enter them in the notebook when asked and never commit them to a fork. The relay
address is built into the package (`toffoli_challenge.RELAY_URL`), so there is
nothing else to configure.

## Package layout

`toffoli_challenge` contains client-side helpers only. In particular, it has no
GitLab credential and no hidden noise model. The deployed relay is the only
component that communicates with the private GitLab project.

The known-noise simulator is intentionally transparent. The mystery backend is
a remote client; its actual model is held by the organizers.

`tests/` contains smoke tests (`python -m pytest tests`), and
`.github/workflows/smoke-test.yml` runs them plus the full notebook on every push.

## Helper API

The notebook does not define submission validation, result parsing, or scoring
logic. It imports the documented functions below from `toffoli_challenge`.

```python
from getpass import getpass

from toffoli_challenge import (
    baseline_native_toffoli,
    validate_submission_circuit,
    compare_to_toffoli,
    load_submission_qasm,
    truth_table_row,
    with_input_preparation,
    connect_team,
    submit_circuit,
    fetch_my_results,
    results_by_queue_id,
    truth_table_from_results,
)
from toffoli_challenge.known_noise import known_noise_truth_table

# A valid native-gate Toffoli to beat (Qiskit's automatic compilation).
candidate_circuit = baseline_native_toffoli()

# Check the submitted three-qubit, measurement-free native circuit.
validate_submission_circuit(candidate_circuit)

# Check its ideal unitary before any hardware use.
max_error, process_fidelity, average_gate_fidelity = compare_to_toffoli(candidate_circuit)

# Estimate its eight-input truth-table success rate under the disclosed noise model.
print(known_noise_truth_table(candidate_circuit, shots=1024).mean_success_probability)

# Reload a circuit saved with qasm2.dumps (plain qasm2.load rejects rxx).
reloaded = load_submission_qasm("my_circuit.qasm")

# The lab runs each submission once, as written, from |000>, and returns one
# file <queueID>_<shots>_<teamID>.txt. A truth table is therefore eight
# submissions, one per input, each prepared with native rx(pi) flips.
connect_team("your_team_id", getpass())
queue_id_by_input = {}
for input_bits in ["000", "001", "010", "011", "100", "101", "110", "111"]:
    receipt = submit_circuit(with_input_preparation(candidate_circuit, input_bits), shots=64)
    queue_id_by_input[input_bits] = receipt["submission"]["queue_id"]

# Later, once the lab has run them:
returned = fetch_my_results()
print(results_by_queue_id(returned))            # {queue_id: [bitstrings], ...}
print(truth_table_from_results(returned, queue_id_by_input).mean_success_probability)

# Compare a single raw list with the ideal output for input c1c2t = 110.
single = truth_table_row("110", ["111"] * 60 + ["110"] * 4)
print(single.success_probability)  # 0.9375
```

These helpers are for analysis. Anything in your own fork can be edited, so the
judges may recompute any hardware number you present directly from the lab's
raw result files: keep the queue IDs (and IonQ job IDs) behind every claim.
