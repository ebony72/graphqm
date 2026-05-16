# Derived from Qiskit (Apache License 2.0, IBM 2017-2020).
"""SABRE swap-insertion pass with optional bridge-gate support.

Heuristics ('basic' | 'lookahead' | 'decay') follow Li et al., ASPLOS 2019
(arXiv:1809.02573). When ``use_bridge=True``, a distance-2 CX in the front
layer may be emitted as four nearest-neighbor CXs (a "bridge" decomposition)
instead of inserting a SWAP.
"""

import logging
from collections import defaultdict
from copy import copy, deepcopy

import numpy as np

from qiskit.circuit.library.standard_gates import SwapGate, CXGate
from qiskit.circuit import Qubit
from qiskit.dagcircuit import DAGOpNode
from qiskit.transpiler.basepasses import TransformationPass
from qiskit.transpiler.exceptions import TranspilerError
from qiskit.transpiler.layout import Layout

logger = logging.getLogger(__name__)


class SabreSwap(TransformationPass):
    """Map a circuit onto a backend topology via SWAP (and optional bridge) insertion.

    Heuristics:
      - 'basic'     : sum of distances over the front layer.
      - 'lookahead' : basic + ``extended_set_weight`` * basic-on-extended-set.
      - 'decay'     : lookahead * max(recency_decay) on the two swap qubits.

    Bridge: when enabled, a distance-2 CX(a,c) in the front layer can be emitted
    as CX(a,b), CX(b,c), CX(a,b), CX(b,c) through an intermediate physical
    qubit b, instead of inserting a SWAP. Layout is unchanged in that case.
    """

    def __init__(
        self,
        coupling_map,
        heuristic="basic",
        seed=None,
        fake_run=False,
        use_bridge=False,
        extended_set_size=20,
        extended_set_weight=0.5,
        decay_rate=0.001,
        decay_reset_interval=5,
    ):
        super().__init__()
        if coupling_map is None or coupling_map.is_symmetric:
            self.coupling_map = coupling_map
        else:
            self.coupling_map = deepcopy(coupling_map)
            self.coupling_map.make_symmetric()

        self.heuristic = heuristic
        self.seed = seed
        self.fake_run = fake_run
        self.use_bridge = use_bridge
        self.extended_set_size = extended_set_size
        self.extended_set_weight = extended_set_weight
        self.decay_rate = decay_rate
        self.decay_reset_interval = decay_reset_interval

        self.applied_predecessors = None
        self.qubits_decay = None
        self._bit_indices = None
        self.dist_matrix = None

    def run(self, dag):
        if len(dag.qregs) != 1 or dag.qregs.get("q", None) is None:
            raise TranspilerError("SabreSwap runs on physical circuits only.")
        if len(dag.qubits) > self.coupling_map.size():
            raise TranspilerError("More virtual qubits exist than physical.")

        self.dist_matrix = self.coupling_map.distance_matrix
        rng = np.random.default_rng(self.seed)

        mapped_dag = None
        if not self.fake_run:
            mapped_dag = dag.copy_empty_like()

        canonical_register = dag.qregs["q"]
        current_layout = Layout.generate_trivial_layout(canonical_register)
        self._bit_indices = {bit: idx for idx, bit in enumerate(canonical_register)}
        self.qubits_decay = {qubit: 1 for qubit in dag.qubits}

        bridge_count = 0
        swap_count = 0
        num_search_steps = 0

        front_layer = dag.front_layer()
        self.applied_predecessors = defaultdict(int)
        for _, input_node in dag.input_map.items():
            for successor in self._successors(input_node, dag):
                self.applied_predecessors[successor] += 1

        while front_layer:
            execute_gate_list = []
            for node in front_layer:
                if len(node.qargs) == 2:
                    v0, v1 = node.qargs
                    if self.coupling_map.graph.has_edge(
                        current_layout._v2p[v0], current_layout._v2p[v1]
                    ):
                        execute_gate_list.append(node)
                else:
                    execute_gate_list.append(node)

            if execute_gate_list:
                for node in execute_gate_list:
                    self._apply_gate(mapped_dag, node, current_layout, canonical_register)
                    front_layer.remove(node)
                    for successor in self._successors(node, dag):
                        self.applied_predecessors[successor] += 1
                        if self._is_resolved(successor):
                            front_layer.append(successor)
                    if node.qargs and self.heuristic == "decay":
                        self._reset_qubits_decay()
                continue

            # No directly applicable gate: pick a SWAP (or bridge, if enabled).
            extended_set = self._obtain_extended_set(dag, front_layer)
            swap_candidates = self._obtain_swaps(front_layer, current_layout)
            swap_scores = dict.fromkeys(swap_candidates, 0)
            for swap_qubits in swap_scores:
                trial_layout = current_layout.copy()
                trial_layout.swap(*swap_qubits)
                swap_scores[swap_qubits] = self._score_heuristic(
                    front_layer, extended_set, trial_layout, swap_qubits
                )
            best_score = min(swap_scores.values())

            if self.use_bridge:
                bridges = self._obtain_bridges(dag, front_layer, current_layout)
                if bridges:
                    prescore = self._score_heuristic(
                        front_layer, extended_set, current_layout, swap_qubits=None
                    )
                    best_bridge_score = max(bridges.values())
                    if prescore - best_score <= best_bridge_score:
                        best_bridges = [k for k, v in bridges.items() if v == best_bridge_score]
                        best_bridge = rng.choice(best_bridges)
                        self._apply_bridge_gate(
                            mapped_dag, best_bridge, current_layout, canonical_register
                        )
                        front_layer.remove(best_bridge)
                        bridge_count += 1
                        for successor in self._successors(best_bridge, dag):
                            self.applied_predecessors[successor] += 1
                            if self._is_resolved(successor):
                                front_layer.append(successor)
                        continue

            best_swaps = [k for k, v in swap_scores.items() if v == best_score]
            best_swaps.sort(key=lambda x: (self._bit_indices[x[0]], self._bit_indices[x[1]]))
            best_swap = rng.choice(best_swaps)
            swap_node = DAGOpNode(op=SwapGate(), qargs=best_swap)
            self._apply_gate(mapped_dag, swap_node, current_layout, canonical_register)
            current_layout.swap(*best_swap)
            swap_count += 1

            if self.heuristic == "decay":
                num_search_steps += 1
                if num_search_steps % self.decay_reset_interval == 0:
                    self._reset_qubits_decay()
                else:
                    self.qubits_decay[best_swap[0]] += self.decay_rate
                    self.qubits_decay[best_swap[1]] += self.decay_rate

        self.property_set["final_layout"] = current_layout
        self.property_set["swap_count"] = swap_count
        self.property_set["bridge_count"] = bridge_count

        logger.info("SabreSwap done: swaps=%d, bridges=%d", swap_count, bridge_count)
        if not self.fake_run:
            return mapped_dag
        return dag

    # ----- gate application -----

    def _apply_gate(self, mapped_dag, node, current_layout, canonical_register):
        if self.fake_run:
            return
        new_node = _transform_gate_for_layout(node, current_layout, canonical_register)
        mapped_dag.apply_operation_back(new_node.op, new_node.qargs, new_node.cargs)

    def _apply_bridge_gate(self, mapped_dag, bridge_gate, current_layout, canonical_register):
        """Decompose a distance-2 CX(a,c) into 4 nearest-neighbor CXs."""
        if self.fake_run:
            return
        if bridge_gate.op.name != "cx":
            raise TranspilerError(
                f"Bridge decomposition only defined for CX, got {bridge_gate.op.name}"
            )

        v_a, v_c = bridge_gate.qargs
        p_a = current_layout._v2p[v_a]
        p_c = current_layout._v2p[v_c]
        common = set(self.coupling_map.neighbors(p_a)) & set(self.coupling_map.neighbors(p_c))
        if not common:
            raise TranspilerError(
                f"Bridge requires distance 2: physical {p_a}, {p_c} share no neighbor"
            )
        p_b = min(common)
        p2v = {p: v for v, p in current_layout._v2p.items()}
        v_b = p2v[p_b]

        cx = CXGate()
        for q1, q2 in ((v_a, v_b), (v_b, v_c), (v_a, v_b), (v_b, v_c)):
            node = DAGOpNode(op=cx, qargs=[q1, q2])
            self._apply_gate(mapped_dag, node, current_layout, canonical_register)

    # ----- DAG helpers -----

    def _reset_qubits_decay(self):
        self.qubits_decay = {k: 1 for k in self.qubits_decay}

    def _successors(self, node, dag):
        for _, successor, edge_data in dag.edges(node):
            if isinstance(successor, DAGOpNode) and isinstance(edge_data, Qubit):
                yield successor

    def _is_resolved(self, node):
        return self.applied_predecessors[node] == len(node.qargs)

    # ----- swap / bridge candidates -----

    def _obtain_bridges(self, dag, front_layer, layout):
        """{distance-2 CX in front_layer: # of immediate nn-distance-1 successors}."""
        bridges = {}
        for node in front_layer:
            if len(node.qargs) != 2 or node.op.name != "cx":
                continue
            if self.dist_matrix[layout._v2p[node.qargs[0]], layout._v2p[node.qargs[1]]] != 2:
                continue
            solvable = 0
            for suc in self._successors(node, dag):
                if (
                    len(suc.qargs) == 2
                    and self.dist_matrix[
                        layout._v2p[suc.qargs[0]], layout._v2p[suc.qargs[1]]
                    ]
                    == 1
                ):
                    solvable += 1
            bridges[node] = solvable
        return bridges

    def _obtain_extended_set(self, dag, front_layer):
        extended_set = []
        incremented = []
        tmp_front_layer = front_layer
        done = False
        while tmp_front_layer and not done:
            new_tmp_front_layer = []
            for node in tmp_front_layer:
                for successor in self._successors(node, dag):
                    incremented.append(successor)
                    self.applied_predecessors[successor] += 1
                    if self._is_resolved(successor):
                        new_tmp_front_layer.append(successor)
                        if len(successor.qargs) == 2:
                            extended_set.append(successor)
                if len(extended_set) >= self.extended_set_size:
                    done = True
                    break
            tmp_front_layer = new_tmp_front_layer
        for node in incremented:
            self.applied_predecessors[node] -= 1
        return extended_set

    def _obtain_swaps(self, front_layer, current_layout):
        candidate_swaps = set()
        for node in front_layer:
            for virtual in node.qargs:
                physical = current_layout[virtual]
                for neighbor in self.coupling_map.neighbors(physical):
                    virtual_neighbor = current_layout[neighbor]
                    swap = sorted(
                        [virtual, virtual_neighbor], key=lambda q: self._bit_indices[q]
                    )
                    candidate_swaps.add(tuple(swap))
        return candidate_swaps

    # ----- scoring -----

    def _compute_cost(self, layer, layout):
        cost = 0
        layout_map = layout._v2p
        for node in layer:
            if len(node.qargs) != 2:
                continue
            cost += self.dist_matrix[layout_map[node.qargs[0]], layout_map[node.qargs[1]]]
        return cost

    def _score_heuristic(self, front_layer, extended_set, layout, swap_qubits=None):
        first_cost = self._compute_cost(front_layer, layout)
        if self.heuristic == "basic":
            return first_cost
        first_cost /= len(front_layer)
        second_cost = 0
        if extended_set:
            second_cost = self._compute_cost(extended_set, layout) / len(extended_set)
        total = first_cost + self.extended_set_weight * second_cost
        if self.heuristic == "lookahead":
            return total
        if self.heuristic == "decay":
            return (
                max(self.qubits_decay[swap_qubits[0]], self.qubits_decay[swap_qubits[1]])
                * total
            )
        raise TranspilerError(f"Heuristic {self.heuristic!r} not recognized.")


def _transform_gate_for_layout(op_node, layout, device_qreg):
    """Return a node whose qargs are replaced by the current physical positions."""
    mapped = copy(op_node)
    mapped.qargs = [device_qreg[layout._v2p[q]] for q in op_node.qargs]
    return mapped
