import networkx as nx
import pytest

from vfsexp import Vf


def _is_valid_subgraph_map(mapping, sub, big):
    """Return True if `mapping` is a node injection that preserves all edges of `sub`."""
    if set(mapping.keys()) != set(sub.nodes()):
        return False
    if len(set(mapping.values())) != len(mapping):
        return False
    for u, v in sub.edges():
        if not big.has_edge(mapping[u], mapping[v]):
            return False
    return True


def test_triangle_into_k4_dfsmatch():
    sub = nx.complete_graph(3)
    big = nx.complete_graph(4)
    vf = Vf(sub, big, {}, stop=10)
    result = vf.dfsMatch({})
    assert _is_valid_subgraph_map(result, sub, big)


def test_path_p3_into_path_p5():
    sub = nx.path_graph(3)
    big = nx.path_graph(5)
    vf = Vf(sub, big, {}, stop=10)
    result = vf.dfsMatch({})
    assert _is_valid_subgraph_map(result, sub, big)


def test_dfsmatchall_counts_k3_in_k4():
    """K3 has 4 * 3 * 2 = 24 ordered embeddings in K4."""
    sub = nx.complete_graph(3)
    big = nx.complete_graph(4)
    vf = Vf(sub, big, {}, stop=10)
    all_maps = vf.dfsMatchAll([])
    assert len(all_maps) == 24
    for m in all_maps:
        assert _is_valid_subgraph_map(m, sub, big)


def test_no_embedding_k4_in_path():
    """K4 has a triangle; a path of 5 doesn't, so no embedding exists."""
    sub = nx.complete_graph(4)
    big = nx.path_graph(5)
    vf = Vf(sub, big, {}, stop=10)
    result = vf.dfsMatch({})
    assert len(result) < sub.number_of_nodes()


def test_dfsmatchbest_prefers_close_to_premap():
    """With a feasible identity preMap, dfsMatchBest should find a zero-distance map."""
    sub = nx.complete_graph(3)
    big = nx.complete_graph(5)
    pre_map = {0: 0, 1: 1, 2: 2}
    vf = Vf(sub, big, {}, stop=10, preMap=pre_map, upperbound=100)
    result = vf.dfsMatchBest({})
    assert _is_valid_subgraph_map(result, sub, big)
    total_distance = sum(
        nx.shortest_path_length(big, pre_map[k], result[k]) for k in result
    )
    assert total_distance == 0
