#!/usr/bin/env python3
"""compare.py — side-by-side benchmark of graphqm vs upstream Qiskit SABRE.

For each benchmark circuit, runs both pipelines on the IBM Q Tokyo (q20)
coupling map and reports SWAP counts.

The graphqm pipeline mirrors `dac_router_all.ipynb`:
    partition the reduced circuit into AG-embeddable sections, find an initial
    mapping for section 0 via Vf, then for each subsequent section call
    `connect_two.iterative_dfs` to compute the SWAP sequence that transforms
    the current mapping into one valid for that section.

Requirements:
    - Qiskit 0.33 (graphqm modules use private APIs like `Qubit._index`).
    - graphqm repo on PYTHONPATH (handled if you run from the repo root).
    - Benchmark QASM files at $GRAPHQM_BENCH
      (default: `../bench/qiskit_circuit_benchmark/`).

Usage:
    cd graphqm
    python scripts/compare.py
"""

import copy
import os
import sys

# Make repo-root modules importable regardless of cwd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import networkx as nx
from qiskit import QuantumCircuit
from qiskit.converters import circuit_to_dag, dag_to_circuit
from qiskit.dagcircuit import DAGOpNode
from qiskit.transpiler import CouplingMap, PassManager
from qiskit.transpiler.passes import SabreLayout, SabreSwap
from qiskit.transpiler.passes.layout.apply_layout import ApplyLayout
from qiskit.transpiler.passes.layout.enlarge_with_ancilla import EnlargeWithAncilla
from qiskit.transpiler.passes.layout.full_ancilla_allocation import FullAncillaAllocation

import ag
from config import BENCH_PATH
from connect_two import iterative_dfs
from connect_two import swap as connect_two_swap
from dac_part import (
    graph_of_circuit,
    is_embeddable,
    partition,
    remove_1q_and_consecutive_2q_gates_in_circuit,
)


CIRCUITS = [
    "qft_10.qasm",
    "qft_16.qasm",
    "grover_operator_6.qasm",
    "grover_operator_10.qasm",
    "phase_estimation_10.qasm",
    "phase_oracle_10.qasm",
    "AND_10.qasm",
    "excitation_preserving_10.qasm",
    "quantum_volume_10.qasm",
    "quantum_volume_16.qasm",
]
SABRE_SEEDS = [42, 7, 100, 314, 999]


def run_sabre(qc, cm, seed):
    """SabreLayout + SabreSwap with the lookahead heuristic. Returns SWAP count."""
    layout = SabreLayout(cm, routing_pass=SabreSwap(cm, "lookahead", seed=seed), seed=seed)
    pm = PassManager(
        [
            layout,
            FullAncillaAllocation(cm),
            EnlargeWithAncilla(),
            ApplyLayout(),
            SabreSwap(cm, "lookahead", seed=seed),
        ]
    )
    out = pm.run(qc)
    return out.count_ops().get("swap", 0)


def _map_completion_all(tau, dag, AG):
    """Extend a partial token->node map by greedy nearest-neighbor placement.

    Re-implementation of dac_router_all.ipynb cell 0's map_completion_all.
    """
    SPL = {(p, q): nx.shortest_path_length(AG, p, q) for p in AG.nodes() for q in AG.nodes()}
    for node in dag.topological_op_nodes():
        if len(tau) == len(dag.qubits):
            return tau
        if not isinstance(node, DAGOpNode):
            continue
        token1, token2 = node.qargs[0]._index, node.qargs[1]._index
        if token1 in tau and token2 not in tau:
            u = tau[token1]
            cands = [(v, SPL[(u, v)]) for v in AG.nodes() if v not in tau.values()]
            tau[token2] = sorted(cands, key=lambda x: x[1])[0][0]
        elif token2 in tau and token1 not in tau:
            u = tau[token2]
            cands = [(v, SPL[(u, v)]) for v in AG.nodes() if v not in tau.values()]
            tau[token1] = sorted(cands, key=lambda x: x[1])[0][0]
        elif token1 not in tau and token2 not in tau:
            occ = list(tau.values())
            best_dist = 2 * nx.diameter(AG) if occ else 0
            best_edge = None
            for edge in AG.edges():
                u, v = edge
                if u in tau.values() or v in tau.values():
                    continue
                if not occ:
                    best_edge = (u, v)
                    break
                cu = min(nx.shortest_path_length(AG, u, o) for o in occ)
                cv = min(nx.shortest_path_length(AG, v, o) for o in occ)
                if cu + cv < best_dist:
                    best_dist = cu + cv
                    best_edge = (u, v)
            if best_edge is not None:
                tau[token1], tau[token2] = best_edge
    return tau


def run_graphqm(qc, AG):
    """Partition + connect_two routing. Returns (swap_count, num_sections).

    Deterministic given the inputs (no randomness in partition / iterative_dfs /
    map_completion_all), so no seed parameter is needed.
    """
    newcirc = remove_1q_and_consecutive_2q_gates_in_circuit(qc)
    tokenset = set(q._index for q in newcirc.qubits)
    dag = circuit_to_dag(newcirc)

    sections = partition(dag, AG, method="greedy")
    num_sections = len(sections)
    if num_sections == 1:
        return 0, 1

    cur_graph = graph_of_circuit(dag_to_circuit(sections[0]))
    ok, inimap = is_embeddable(cur_graph, AG, 10)
    if not ok:
        raise RuntimeError("section 0 not embeddable into AG")

    tau = copy.copy(inimap)
    if len(tau) < len(tokenset):
        tau = _map_completion_all(tau, dag, AG)
    cur_map = copy.copy(tau)

    map_id = {v: v for v in AG.nodes()}
    total_swaps = 0
    for i in range(1, num_sections):
        sec_graph = graph_of_circuit(dag_to_circuit(sections[i]))
        constraints = [
            (cur_map[u], cur_map[v])
            for (u, v) in sec_graph.edges()
            if u in cur_map and v in cur_map
        ]
        action = iterative_dfs(map_id, constraints, AG)
        if action is None:
            raise RuntimeError(f"routing failed at section transition {i}")
        total_swaps += len(action)
        for edge in action:
            cur_map = connect_two_swap(edge, cur_map, AG)

    return total_swaps, num_sections


def main():
    AG = ag.q20()
    cm = CouplingMap(list(AG.edges()))
    bench = os.environ.get("GRAPHQM_BENCH", BENCH_PATH)

    print(f"Benchmarks from: {bench}")
    print(
        f"Architecture:    q20 (IBM Tokyo), "
        f"{AG.number_of_nodes()} qubits, {AG.number_of_edges()} edges"
    )
    print(f"SABRE seeds:     {SABRE_SEEDS} (best taken)")
    print(f"graphqm:         deterministic, single run")
    print()
    header = f"{'circuit':<32}{'qubits':>8}{'cx_in':>8}{'sabre':>8}{'graphqm':>10}{'parts':>8}  notes"
    print(header)
    print("-" * len(header))

    for fn in CIRCUITS:
        path = os.path.join(bench, fn)
        if not os.path.exists(path):
            print(f"{fn:<32}  SKIP (not found)")
            continue
        with open(path) as f:
            qc = QuantumCircuit.from_qasm_str(f.read())
        cx_in = qc.count_ops().get("cx", 0)

        sabre_sw = min(run_sabre(qc, cm, s) for s in SABRE_SEEDS)

        try:
            gqm_sw, gqm_parts = run_graphqm(qc, AG)
            gqm_disp, parts_disp, note = str(gqm_sw), str(gqm_parts), ""
        except Exception as e:
            gqm_disp, parts_disp, note = "—", "—", f"FAIL: {type(e).__name__}: {e}"

        print(
            f"{fn:<32}{qc.num_qubits:>8}{cx_in:>8}{sabre_sw:>8}"
            f"{gqm_disp:>10}{parts_disp:>8}  {note}"
        )


if __name__ == "__main__":
    main()
