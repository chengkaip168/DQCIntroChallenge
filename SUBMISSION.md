# DQC Challenge: our submission

We claim D1c, the Toffoli construction of Barenco et al. (*Phys. Rev. A* 52, 3457, 1995) built from the native gates, with each run of one-qubit gates merged into `rz` and `ry`. On the DQC lab, the one machine that ran our circuits exactly as written, it tied the starter kit's baseline D0 and beat both of our calibrated designs, and our claim rule, fixed before the results, breaks the tie in its favor. On IonQ's Forte 1, with every gate running in IonQ's native gates, D1c and D0 were tied as well. Its OpenQASM, from `qasm2.dumps`, is in `evidence/D1c_claimed.qasm`.

Our case, answering the questions of the starter notebook's Section 10, is in Section 10 of `notebooks/Toffoli_Hardware_Hackathon_Challenge.ipynb`. All our work, with every output, is in `notebooks/team_toffoli.ipynb`.

## Results

"Best" means the highest process fidelity, estimated by a fidelity range from three test sets (24 circuits per design), ranked on its raw lower end F_LB. Two designs differ only if their gap is larger than 2σ of the difference; otherwise they are tied. Every comparison below ran side by side, in one batch.

| Machine | Designs side by side (raw F_LB) | Verdict |
|---|---|---|
| DQC lab, round 1 | D1c 0.752 ± 0.015, D0 0.727 ± 0.016, D2 0.661 ± 0.017 | D1c and D0 tied; both better than D2 |
| DQC lab, round 2 | D1c 0.756 ± 0.015, D3 0.699 ± 0.017 | D1c better |
| IonQ Forte 1, native gates (supplementary), 06:16 | D1c 0.912 ± 0.003, D0 0.906 ± 0.003 | tied |
| IonQ Forte 1, native gates (supplementary), 07:22 | D1c 0.906 ± 0.003, D0 0.906 ± 0.003, D5 0.896 ± 0.004 | D1c and D0 tied; D5 just behind D0 and tied with D1c |

D0 is the starter kit's baseline. D2 and D3 are D0 with each `rxx` angle changed to cancel a measured error (Section 5), and D5 is D0 with angles fitted to IonQ's compiled circuits (Section 8.7).

IonQ's cloud compiler rewrote our main Forte 1 runs before running them, and removed every entangling gate from D1c's test circuits, so those runs do not compare our designs. Section 8.9 shows this from the circuits IonQ actually ran, saved in `evidence/ionq/forte1_compiled_native_circuits.json`. For the native-gate run we translated D0 and D1c gate by gate into IonQ's native gates, so that every `rxx` runs (Section 8.10). We sent it before an organizer had said whether native gates are allowed, so we report it as supplementary.

## Where everything is

| What | Where |
|---|---|
| Our case (the starter notebook's Section 10) | `notebooks/Toffoli_Hardware_Hackathon_Challenge.ipynb` |
| All our work, with outputs | `notebooks/team_toffoli.ipynb`: Decisions, then Sections 0 to 9 |
| The circuit we claim | `evidence/D1c_claimed.qasm` |
| Lab queue IDs, one row per circuit (148 circuits) | `evidence/queue_ids.csv` |
| IonQ job IDs, one row per circuit | `evidence/ionq_jobs.csv` |
| Raw IonQ counts, the circuits of each job, and the circuits IonQ actually ran | `evidence/ionq/` |

## How to check a number

For a lab number, every circuit's queue ID, design, test and shots are in `evidence/queue_ids.csv`. `fetch_my_results(queue_id=...)` returns its raw file, and Sections 4.5 and 4.6 of `team_toffoli.ipynb` turn raw files into the numbers above.

For an IonQ number, `evidence/ionq/` has each job's circuits (with their QASM) and raw counts, and Section 8 recomputes every IonQ number from those files without an IonQ key. The job IDs in `evidence/ionq_jobs.csv` can be looked up in the team's IonQ project.

## How to rerun

Install the starter kit's environment (`requirements.txt`, plus `requirements-ionq.txt` for Section 8) and run `team_toffoli.ipynb` from the top. Every cell that can send to hardware has SUBMIT = False, so a full run sends nothing. Without lab credentials the lab cells say so, and without an IonQ key Section 8 reads the saved IonQ results. The frozen fit in Section 8.7 takes about 15 minutes, and the repeated blind test in Section 9.1 about 6.

## The night in short

| Time | Step |
|---|---|
| 16:59 | Lab round 1A: readout check and gate probes |
| 17:15 to 18:22 | Lab round 1: D0, D1c and D2 (D0 calibrated from the probes) side by side |
| 21:04 | D3: D0 calibrated by fitting round 1's circuits (method 2) |
| 21:42 to 21:44 | Lab round 2: D1c and D3, and a second probe, which showed the `rxx` angles had drifted by up to 0.2 rad |
| 21:50 | Claim rule fixed, before any round 2 result |
| 22:15 | Lab claim: D1c |
| 22:49 to 00:49 | Method 2 tested blind on simulated machines (Section 9); a fitting bug found and fixed; the fit frozen at 00:44 |
| 00:40 to 00:43 | Free rehearsal on IonQ's simulator |
| 01:45 to 04:34 | Forte 1 batch 1 |
| 05:10 to 05:31 | Forte 1 batch 2: D1c, D5 and D6 |
| 05:55 | Reading back the circuits IonQ ran: its compiler had removed the entangling gates from many test circuits, including all of D1c's |
| 06:16 to 06:58 | Forte 1 native-gate run of D0 and D1c, so that every gate runs: tied |
| 07:22 | Forte 1 native-gate run of D1c, D5 and D0: D5 no better than either |
| 07:53 | Forte 1 native-gate run of D1c, D6 and D0, not back when this was written |
