# graphqm — Graph-theoretic Qubit Mapping

Research code exploring qubit mapping on NISQ devices via graph theory.

## Approach

1. **Partition** a circuit into sections whose interaction graphs are each subgraph-isomorphic to the device's architecture graph (so no SWAPs are needed within a section).
2. **Connect** consecutive sections via token-swap routing under the constraints imposed by the next section's interaction graph.
3. **Augment SABRE** with bridge gates as an alternative to SWAP insertion.
4. **Profile** circuits — interaction graph, layer distribution per edge, cutting points.
5. **Benchmark** against vanilla Qiskit SABRE and StochasticSwap.

Sibling work to [FiDLS](https://github.com/ebony72/FiDLS) and [quekno](https://github.com/ebony72/quekno).

## Modules

| File | Purpose |
| --- | --- |
| `ag.py` | Architecture graphs: `q20` (IBM Tokyo), `qgrid`, `rochester`, `sycamore`, `Sycamore54Q`, `guadalupe` |
| `vfsexp.py` | VF2-style subgraph isomorphism: `dfsMatch` / `dfsMatchBest` / `dfsMatchAll` |
| `dac_part.py` | Divide-and-conquer DAG partitioning into AG-embeddable sections; cutting points |
| `connect_two.py` | Token-swap routing between sub-mappings via constraint satisfaction |
| `sabre_swap.py` | SABRE swap pass; heuristic in `{basic, lookahead, decay}`; bridge gates via `use_bridge=True` |
| `sabre_layout.py` | Forward-backward SabreLayout |
| `config.py` | Benchmark path config (override via `GRAPHQM_BENCH` env var) |

## Notebooks

Experiment drivers — e.g. `dac_router_*.ipynb`, `lisabre_run.ipynb`, `graph_profile.ipynb`, `sabre_example_2310.ipynb`.

## Setup

```bash
pip install -r requirements.txt
```

Benchmarks default to `../bench/qiskit_circuit_benchmark/`. Override with `export GRAPHQM_BENCH=/path/to/qasm/` and `from config import BENCH_PATH` in new code (older notebooks still have the path hardcoded).

## Dependencies

Pinned to Qiskit 0.33; some files use private APIs (`Qubit._index`, `DAGOpNode` constructor) that may break on newer versions.
