import networkx as nx
import pytest

import ag


def test_q20_size():
    g = ag.q20()
    assert g.number_of_nodes() == 20
    assert set(g.nodes()) == set(range(20))
    assert nx.is_connected(g)


def test_qgrid_2x2():
    g = ag.qgrid(2, 2)
    assert g.number_of_nodes() == 4
    assert set(g.nodes()) == set(range(4))
    assert g.number_of_edges() == 4
    assert nx.is_connected(g)


def test_qgrid_3x4():
    g = ag.qgrid(3, 4)
    assert g.number_of_nodes() == 12
    assert set(g.nodes()) == set(range(12))
    # m*(n-1) + (m-1)*n edges in an m x n grid
    assert g.number_of_edges() == 3 * 3 + 2 * 4
    assert nx.is_connected(g)


def test_sycamore_54q_size():
    g = ag.Sycamore54Q()
    assert g.number_of_nodes() == 54
    assert g.number_of_edges() == 88


def test_sycamore_removes_node_3():
    """`sycamore()` drops node 3 and relabels — 53 nodes, contiguous 0..52."""
    g = ag.sycamore()
    assert g.number_of_nodes() == 53
    assert set(g.nodes()) == set(range(53))


def test_rochester_size():
    g = ag.rochester()
    assert g.number_of_nodes() == 53


def test_guadalupe_size():
    g = ag.guadalupe()
    assert g.number_of_nodes() == 16
    assert nx.is_connected(g)
