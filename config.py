"""Project-wide config. Override via environment variables.

Set ``GRAPHQM_BENCH`` to point at your QASM benchmark directory; falls back to
the historical relative path so existing notebooks keep working.
"""

import os

BENCH_PATH = os.environ.get("GRAPHQM_BENCH", "../bench/qiskit_circuit_benchmark/")
