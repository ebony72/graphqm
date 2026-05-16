""" This is a py version of dac_router.ipynb @19/09/23"""

from qiskit.transpiler.passes.routing.algorithms.token_swapper import ApproximateTokenSwapper as ATS
from qiskit import QuantumCircuit, QuantumRegister
from qiskit.dagcircuit import DAGCircuit, DAGOpNode, DAGInNode, DAGOutNode
from qiskit.converters import circuit_to_dag, dag_to_circuit
from qiskit.transpiler.layout import Layout
from qiskit.circuit import Qubit
from qiskit.visualization import dag_drawer

import matplotlib.pyplot as plt
import networkx as nx
import rustworkx as rx

import copy, random, time


def get_reverse_mapping(map1):
    revmap = dict()
    for key in map1:
        revmap[map1[key]] = key
    return revmap

""" get an rxgraph from a nxgraph"""
def get_rxgraph(graph):
    if not isinstance(graph,nx.Graph):
        raise Exception (f'The input {type(graph)} should be a nx.Graph')
    rxgraph = rx.PyGraph()
    rxedges = [(edge[0],edge[1],1) for edge in graph.edges()]
    rxgraph.add_nodes_from(graph.nodes())
    rxgraph.add_edges_from(rxedges)
    return rxgraph

def token_swap(permutation, rxAG):
    """permutation is interpreted as a node-to-token mapping, rxAG is the rx version of AG"""
    token_swapper = ATS(rxAG)
    #map1 = get_reverse_mapping(t2nmap)
    action = token_swapper.map(permutation)
    return action

def extend_map(tau1, tau2, rxAG, token):
    dist = rx.distance_matrix(rxAG)
    if token in tau1 or not(token in tau2): 
        raise Exception ('This case will be discussed later.')
    if tau2[token] not in tau1.values():
        print(f'extended {token, tau2[token]}')
        return tau2[token]

    m = len(rxAG.nodes())
    selected_node = None
    for node in rxAG.nodes():
        if node in tau1.values(): continue
        if int(dist[node, tau2[token]]) < m:
            m = int(dist[node, tau2[token]])
            selected_node = node
            
    print(f'extended {token, tau2[token]}')
    return selected_node

def ats_router(tau1, tau2, rxAG):
    """//TODO: What if tau1 and tau2 are partial? (both are token-to-node mappings)
        We need to extend tau1 so that it also covers tokens of tau2."""
   
    print(f'tau1 = {tau1} and tau2 = {tau2}')
    for token in rxAG.nodes():
        if token not in tau1 and token in tau2:
            tau1[token] = extend_map(tau1, tau2, rxAG, token)
                    
        if token not in tau2 and token in tau1:
            tau2[token] = extend_map(tau2, tau1, rxAG, token)

    #Undefined_TOKEN = [token for token in rxAG.nodes() if token not in tau1]
    NonOccupied_NODE1 = [node for node in rxAG.nodes() if node not in tau1.values()]
    NonOccupied_NODE2 = [node for node in rxAG.nodes() if node not in tau2.values()]
    if len(NonOccupied_NODE1) != len(NonOccupied_NODE2):
        raise Exception (f'Undefined_TOKEN and NonOccupied_NODE do not match!')
    
    permutation = dict()    
    for i in range(len(NonOccupied_NODE1)):
        permutation[NonOccupied_NODE1[i]] = NonOccupied_NODE2[i]
        
    tau1_inv = get_reverse_mapping(tau1)
    for v in rxAG.nodes():
        if v in NonOccupied_NODE1: continue
        #print(f'node {v}')
        permutation[v] = tau2[tau1_inv[v]]
        
    print(f'the composed permutation is {permutation}')
    return token_swap(permutation , rxAG)

def constraint_satisfaction_degree(tau, constraints, AG):
    """constraints is a set, and each constraint has form (p,q), where p,q are tokens."""
    """tau: a token-to-node mapping """
    #dist = nx.distance_matrix(AG)

    CSD = dict()
    for (p,q) in constraints:
        if p not in tau or q not in tau: #TODO: This could be refined.
            CSD[(p,q)] = 0
        else:
            CSD[(p,q)] = len(nx.shortest_path(AG, tau[p], tau[q]))-2
        
    return sum(CSD.values())

def constrained_tokens(constraints):
    tokenset = set()
    for c in constraints:
        tokenset.add(c[0])
        tokenset.add(c[1])
    return tokenset

def is_relevant(edge, tau, constraints):
    #u, v = edge
    tokenset = constrained_tokens(constraints)
    tau_inv = get_reverse_mapping(tau)
    
    for x in edge:
        if x in tau.values() and tau_inv[x] in tokenset: 
            return True
    return False

def swap(edge, tau, AG):
    if edge not in AG.edges(): 
        raise Exception (f'{edge} should be an edge in AG!')
    u, v = edge
    tau_inv = get_reverse_mapping(tau)
    #TODO: What if u or v not in tau.values()?

    newtau = copy.copy(tau)
    if u not in tau.values() and v not in tau.values():
        return tau
    elif u in tau.values() and v not in tau.values():
        newtau[tau_inv[u]] = v
    elif u not in tau.values() and v in tau.values():
        newtau[tau_inv[v]] = u
    else:
        p, q = tau_inv[u], tau_inv[v]
        newtau[p], newtau[q] = tau[q], tau[p]
    return newtau
    
def rank_local_actions(tau, constraints, AG):
    preval = constraint_satisfaction_degree(tau, constraints, AG)
    EdgeRelevant = []
    for edge in AG.edges(): 
        if is_relevant(edge, tau, constraints):
            newtau = swap(edge, tau, AG)
            val = constraint_satisfaction_degree(newtau, constraints, AG)
            EdgeRelevant.append([val,edge,newtau])
            
    return sorted(EdgeRelevant, key=lambda x: x[0])
    
    
def optimal_local_actions(tau, constraints, AG):
    sorted_list = rank_local_actions(tau, constraints, AG)
    bestval = sorted_list[0][0]
    return [item[1] for item in sorted_list if item[0]==bestval]

"""We have a counter-example when tau = {0: 1, 1: 5, 2: 0, 3: 2, 4: 3, 5: 4} and 
    constraints = {(4,1),(1,5),(1,3)}, when the greedy search algorithm cannot find a solution.
"""
def random_opt_local(tau, constraints, AG):
    preval = constraint_satisfaction_degree(tau, constraints, AG)
    if preval == 0: 
        #print(f'the constraints are satified {preval, tau}')
        return []
    cur_tau = copy.copy(tau)
    step = 0
    action = []
    while preval > 0 and step <= nx.diameter(AG):
        step += 1
        Candidates = optimal_local_actions(cur_tau,constraints, AG)
        selected_swap = random.choice(Candidates)
        newtau = swap(selected_swap, cur_tau, AG)
        cur_val = constraint_satisfaction_degree(newtau, constraints, AG)
        #print(step, selected_swap, preval, cur_val, cur_tau)
        if cur_val > preval:
            raise Exception (f'We have a situation {cur_tau, selected_swap, preval, cur_val}')
        cur_tau = copy.copy(newtau)
        preval = cur_val
        action.append(selected_swap)
    
    if preval > 0: 
        print(f'Failed! Search end with {preval, step, action, cur_tau}')
    return action

"""An iterative depth-first search strategy"""
def dfs(depth, tau, constraints, AG, deadline=None):
    if deadline is not None and time.monotonic() > deadline:
        return False, []
    preval = constraint_satisfaction_degree(tau, constraints, AG)
    if preval == 0:
        return True, []
    if depth == 0:
        return False, []

    """We prefer edges that reduce the constraint-satisfaction value most."""
    sorted_list = rank_local_actions(tau, constraints, AG)
    Candidates = [item[1] for item in sorted_list]
    # Cap branching to the top-5 sorted candidates. The previous form
    # `Candidates[0:max(5, len(Candidates))]` slices to `max(5, len)` which is
    # always `len` once len >= 5 — i.e. it never actually capped anything.
    for edge in Candidates[0:min(5, len(Candidates))]:
        if is_relevant(edge, tau, constraints):
            newtau = swap(edge, tau, AG)
            success, action = dfs(depth - 1, newtau, constraints, AG, deadline)
            if success:
                return success, [edge] + action
    return False, []


def iterative_dfs(tau, constraints, AG, max_seconds=None):
    """Iterative-deepening DFS over swap edges up to 2*diameter(AG).

    If ``max_seconds`` is set, abort early and return None when the wall clock
    is exceeded — checked between depth iterations and inside the recursive
    dfs. This lets callers fall back to another router without losing the
    whole circuit.
    """
    deadline = time.monotonic() + max_seconds if max_seconds is not None else None
    depth = 2 * nx.diameter(AG)
    for d in range(depth):
        if deadline is not None and time.monotonic() > deadline:
            print(f"iterative_dfs: time budget {max_seconds}s exceeded at depth {d}")
            return None
        success, action = dfs(d, tau, constraints, AG, deadline)
        print(f"test {d, success}")
        if success:
            return action
    print(f'failed after {depth} iterative calls of dfs')
    return None


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
#_________________TEST_____________________________________________________________#
if __name__=='__main__':
    import random
    from ag import q20

    AG = q20()
    V = list(AG.nodes())
    random.shuffle(V)
    print(V)

    tau = dict()
    for i in range(len(AG.nodes())):
        tau[i] = V[i]

    print(f'The input mapping is {tau}')

    #tau = {0:0, 1:1, 2:2, 3:3, 4:4, 5:5}

    #tau = {0: 1, 1: 5, 2: 0, 3: 2, 4: 3, 5: 4}

    constraints = {(4,1),(1,5),(1,3),(5,4)}

    print(f'The input constraints are {constraints}')

    action = random_opt_local(tau, constraints, AG)

    print(f'The generated action is {action}')

    dfs_success, dfs_action = dfs(3,tau,constraints,AG)
    print(dfs_success, dfs_action)
    idfs_action = iterative_dfs(tau,constraints,AG)
    print(idfs_action)