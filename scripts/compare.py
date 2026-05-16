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
    - Qiskit >= 1.0 (tested on 2.3.1).
    - graphqm repo on PYTHONPATH (handled if you run from the repo root).
    - Benchmark QASM files at $GRAPHQM_BENCH
      (default: `../bench/qiskit_circuit_benchmark/`).

Usage:
    cd graphqm
    python scripts/compare.py
"""

import copy
import os
import signal
import sys

# Make repo-root modules importable regardless of cwd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


CIRCUIT_TIMEOUT_S = 300  # per-circuit wall clock for run_graphqm; 0 disables


class CircuitTimeout(Exception):
    pass


def _alarm_handler(signum, frame):
    raise CircuitTimeout()

import networkx as nx
from qiskit import QuantumCircuit
from qiskit.converters import circuit_to_dag, dag_to_circuit
from qiskit.dagcircuit import DAGOpNode
from qiskit.transpiler import CouplingMap, PassManager
from qiskit.transpiler.passes import SabreLayout, SabreSwap
from qiskit.transpiler.passes.layout.apply_layout import ApplyLayout
from qiskit.transpiler.passes.layout.enlarge_with_ancilla import EnlargeWithAncilla
from qiskit.transpiler.passes.layout.full_ancilla_allocation import FullAncillaAllocation

from qiskit.transpiler.passes.routing.algorithms.token_swapper import ApproximateTokenSwapper

import ag
from config import BENCH_PATH
from connect_two import get_rxgraph, iterative_dfs
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


def _ats_fallback_route(cur_map, sec_graph, AG):
    """Route a section transition via ApproximateTokenSwapper when iterative_dfs fails.

    Finds any valid embedding of the section's interaction graph and uses ATS to
    compute the SWAP sequence taking cur_map to that target. Returns
    ``(swap_count, new_cur_map)``.
    """
    ok, target_map = is_embeddable(sec_graph, AG, 30)
    if not ok:
        raise RuntimeError("section IG not embeddable into AG")

    # Build a full permutation over AG nodes from cur_map to target_map
    permutation = {}
    src_positions, dst_positions = set(), set()
    for t in target_map:
        if t not in cur_map:
            continue
        p_curr, p_target = cur_map[t], target_map[t]
        permutation[p_curr] = p_target
        src_positions.add(p_curr)
        dst_positions.add(p_target)
    free_src = [n for n in AG.nodes() if n not in src_positions]
    free_dst = [n for n in AG.nodes() if n not in dst_positions]
    for s, d in zip(free_src, free_dst):
        permutation[s] = d

    rxAG = get_rxgraph(AG)
    swap_list = ApproximateTokenSwapper(rxAG).map(permutation)

    # Walk the swap sequence to update cur_map
    new_cur_map = copy.copy(cur_map)
    inv = {v: k for k, v in new_cur_map.items()}
    for u, v in swap_list:
        tu, tv = inv.get(u), inv.get(v)
        if tu is not None:
            new_cur_map[tu] = v
        if tv is not None:
            new_cur_map[tv] = u
        inv = {val: key for key, val in new_cur_map.items()}

    return len(swap_list), new_cur_map


def run_graphqm(qc, AG, use_ats_fallback=True):
    """Partition + connect_two routing. Returns ``(swap_count, (parts, fallbacks))``.

    Deterministic given the inputs. When ``use_ats_fallback`` is True (default),
    a transition that iterative_dfs can't solve falls back to
    ApproximateTokenSwapper so every circuit produces a result.
    """
    newcirc = remove_1q_and_consecutive_2q_gates_in_circuit(qc)
    tokenset = set(q._index for q in newcirc.qubits)
    dag = circuit_to_dag(newcirc)

    sections = partition(dag, AG, method="greedy")
    num_sections = len(sections)
    if num_sections == 1:
        return 0, (1, 0)

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
    fallback_count = 0
    for i in range(1, num_sections):
        sec_graph = graph_of_circuit(dag_to_circuit(sections[i]))
        constraints = [
            (cur_map[u], cur_map[v])
            for (u, v) in sec_graph.edges()
            if u in cur_map and v in cur_map
        ]
        action = iterative_dfs(map_id, constraints, AG)
        if action is None:
            if not use_ats_fallback:
                raise RuntimeError(f"routing failed at section transition {i}")
            n_swaps, cur_map = _ats_fallback_route(cur_map, sec_graph, AG)
            total_swaps += n_swaps
            fallback_count += 1
            continue
        total_swaps += len(action)
        for edge in action:
            cur_map = connect_two_swap(edge, cur_map, AG)

    return total_swaps, (num_sections, fallback_count)


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

        if CIRCUIT_TIMEOUT_S > 0:
            signal.signal(signal.SIGALRM, _alarm_handler)
            signal.alarm(CIRCUIT_TIMEOUT_S)
        try:
            gqm_sw, (gqm_parts, gqm_fb) = run_graphqm(qc, AG)
            note = f"{gqm_fb} ATS fallback(s)" if gqm_fb else ""
            gqm_disp, parts_disp = str(gqm_sw), str(gqm_parts)
        except CircuitTimeout:
            gqm_disp, parts_disp, note = "—", "—", f"TIMEOUT ({CIRCUIT_TIMEOUT_S}s)"
        except Exception as e:
            gqm_disp, parts_disp, note = "—", "—", f"FAIL: {type(e).__name__}: {e}"
        finally:
            if CIRCUIT_TIMEOUT_S > 0:
                signal.alarm(0)

        print(
            f"{fn:<32}{qc.num_qubits:>8}{cx_in:>8}{sabre_sw:>8}"
            f"{gqm_disp:>10}{parts_disp:>8}  {note}"
        )


if __name__ == "__main__":
    main()
