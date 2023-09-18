'''This module constructs weighted graph and topgraph initial mappings ''' 
import networkx as nx
from circ_utils import graph_of_circuit
from graph_utils import hub
from vfs import Vf
'''Always put local parameters before global ones''' 

###\__/#\#/\#\__/#\#/\__/--\__/#\__/#\#/~\
    
def is_embeddable(g, H, anchor, stop):
    '''check if a small graph g is embeddable in a large H, anchor is bool
        g, H (Graph)
        anchor (bool): whether or not mapping anchor of g to that of H
        stop (float): time limit for vf2
    '''
    vf2 = Vf()
    result = {} 
    if anchor: result[hub(g)] = hub(H)
    result = vf2.dfsMatch(g, H, result, stop)
    lng = len(nx.nodes(g))
    if len(result) == lng:
        return True, result   
    return False, result

'''The edge by edge search in 'y' can be sped up if we consider in a bipartite way'''
def top_z_P(i, L_temp, C, G, anchor, stop):
    '''L_temp is the list of the indices of the first cnot gates corresponding to edges in g_of_c'''
    g = nx.Graph()
    for s in L_temp[:i+1]:
        g.add_edge(C[s][0], C[s][1])
    test = is_embeddable(g, G, anchor, stop)
    return test[0]

def search_bipartite_top_z(yes_bound, no_bound, test_number, L_temp, C, G, anchor, stop):
    '''L_temp is the list of the indices of the first cnot gates corresponding to edges in g_of_c'''
    if not type(test_number) == int: raise Exception('Only consider integers')
    if no_bound == yes_bound + 1: return yes_bound
    if top_z_P(test_number, L_temp, C, G, anchor, stop):
        yes_bound = test_number
        if test_number == no_bound: return test_number
        test_number = yes_bound + max(1, (no_bound - yes_bound)//2)
        return search_bipartite_top_z(yes_bound, no_bound, test_number, L_temp, C, G, anchor, stop)
    else:
        if test_number == yes_bound + 1: return yes_bound
        no_bound = test_number
        test_number = yes_bound + max(1, (no_bound - yes_bound)//2)
        return search_bipartite_top_z(yes_bound, no_bound, test_number, L_temp, C, G, anchor, stop)

def best_topgraph_z_ini_mapping(L1, C, G, anchor, stop):
    ''' Test a more efficient way for scanning the gates in C than 'y' by using search_bipartite_top_z'''      
    g = graph_of_circuit(C)
    test = is_embeddable(g, G, anchor, stop)
    if test[0]:
        #print('The graph of the circuit is embeddable in G')
        return g, test[1]
    #print('The graph of the circuit is very likely NOT embeddable in G')    
    L_temp = [] #the index list of first cnot for each edge 
    for edge in g.edges():
        p, q = edge[0], edge[1]
        s = min([k for k in L1 if set(C[k]) == {p,q}]) 
        L_temp.append(s)

    L_temp.sort()
    yes_bound = 0
    no_bound = len(L_temp)
    test_number = no_bound//2
    exact_bound = search_bipartite_top_z(yes_bound, no_bound, test_number, L_temp, C, G, anchor, stop)
            
    g = nx.Graph()
    # add the first edge into g
    for s in L_temp[:exact_bound+1]:
        g.add_edge(C[s][0], C[s][1])
    test = is_embeddable(g, G, anchor, stop)
    if not test[0]: raise Exception('Check why the subgraph is not embeddable!')
    return g, test[1]

###\__/#\#/\#\__/#\#/\__/--\__/#\__/#\#/~\
# the topgraph initial mapping
def topgraph(C, G, anchor, stop):
    ''' Return the topgraph initial mapping

    Args:
        C (list): the input circuit
        G (graph): the architecture graph
    Returns:
        tau (list): the topgraph initial mapping
    '''    
    L = list(range(len(C))) # o in {o,x,y,z}
    tau_dict = best_topgraph_z_ini_mapping(L, C, G, anchor, stop)[1]
    
    return tau_dict
###\__/#\#/\#\__/#\#/\__/--\__/#\__/#\#/~\
