#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# import qiskit
# print(qiskit.__qiskit_version__)
    
from qiskit.transpiler import CouplingMap
from qiskit import QuantumCircuit, QuantumRegister

import ag,time,os
import networkx as nx
import copy


def has_cycle_3(graph):
    for u in graph.nodes():
        for v in graph.neighbors(u):
            for w in graph.neighbors(v):
                if u != w and graph.has_edge(u, w):
                    return True
    return False

def get_a_bounary_edge(H):
    """ Return a best edge to remove """
    candidate = None
    min_deg = 100
    for edge in H.edges():
        p, q  = edge
        if nx.degree(H,p) + nx.degree(H,q) < min_deg:
            min_deg = nx.degree(H,p) + nx.degree(H,q)
            candidate =  edge

    # for edge in H.edges():
    #     p, q  = edge
    #     if nx.degree(H,p) <= 2 and nx.degree(H,q) <= 2:
    #         min_deg = nx.degree(H,p) + nx.degree(H,q)
    #         print(f'The bounary edge is {edge, min_deg}')
    #         return edge
                    
    print(f'The bounary edge is {edge, min_deg}')
    return candidate

# TODO: Return a best 3-node component to remove    
 
# TODO: Return a best k-node component to remove     

# TODO: Fast exclusion
def fast_no_embedding(subgraph, graph):
    # for AG with no 3-cycle
    if has_cycle_3(subgraph) and not has_cycle_3(graph): 
        return True
    
    subgraph_deg = list(nx.degree(subgraph, v) for v in subgraph.nodes())
    subgraph_deg.sort(reverse=True)
    
    graph_deg = list(nx.degree(subgraph, v) for v in subgraph.nodes())
    graph_deg.sort(reverse=True)
    
    l = len(subgraph_deg)
    # if l > len(graph_deg): 
    #     return True
    for idx in range(l):
        if subgraph_deg[idx] > graph_deg[idx]:
            return True
        
    return False



def is_embeddable(g, H, stop, EXP, CLEVER):
    '''check if a small graph g is embeddable in a large H, anchor is bool
        g, H (Graph)
        stop (float): time limit for vf2
        EXP (bool): use vfsexp or vfs?
    '''
    if fast_no_embedding(g, H):
        return False, {}
    
    # if not nx.is_connected(g):
        # print('Attention: The subgraph is not connected!')
        
    # TODO: decomppose g into components and consider each component individually and
    #   if all are embeddable in H, then start form the largest ones
    
    lng = len(nx.nodes(g))
    if not EXP:
        from vfs230503 import Vf    
        
        vf2 = Vf()
        result = vf2.dfsMatch(g, H, {}, stop)
        if len(result) == lng:
            return True, result   
        return False, result
        
    else:            
        from vfsexp import Vf
        """ We may include more parameters """
        
        # CLEVER = True
        
        new_g = g.copy()
        print(len(new_g.edges()) == len(g.edges()))
        
        new_H = H.copy()
        temp_map = dict()
        

        # TODO: how to deal with the case when g is disconnected? 
        # 1. Decompose g into CCs
        # 2. Consider CCs one by one: remove a CC and its image and repeat the procedure for reduced g and H 
        if CLEVER and not nx.is_connected(g):
            
            for c in sorted(nx.connected_components(g), key=len):
                print(f' the cc is {c}')
                if len(c) > 2: continue
                # c_deg = [nx.degree(g, v) for v in c]
                # c_deg.sort(reverse=True)
                # print(c_deg)
                # g_temp = g.subgraph(c)
                # if not is_embeddable(g_temp, H, stop, EXP, False)[0]:
                #     return False, {}
                
                if len(c) == 2:
                    print(f'a small cc {c}')
                    v1, v2 = c
                    u1, u2 = get_a_bounary_edge(new_H)
                    new_H.remove_nodes_from([u1,u2])
                    new_g.remove_nodes_from(c)
                    temp_map[v1] = u1
                    temp_map[v2] = u2
        
        # t = is_embeddable(new_g, new_H, stop, EXP, False)

        vf2 = Vf(new_g, new_H, {}, stop)
        result = vf2.dfsMatch({})
        if len(result) == lng:
            return True, temp_map.update(result)  
        return False, {}

                
        #     print(f'g has {len(list(nx.connected_components(g)))} connected components, which are all embeddable in AG')
            
        #     # Starting with c_max is perhaps not intelligent. We may start with small CCs and remove them from outside to inside.  
        #     c_max = max(nx.connected_components(g), key=len)
            
        #     # print(f' the maximal CC is {c_max}')
        #     deglist = [nx.degree(g, v) for v in c_max]
        #     deglist.sort(reverse=True)
        #     # print(deglist)


        #     g_max_c = g.subgraph(c_max)
            
        #     # This is not a good way, as S may contain >= 100K mappings 
        #     S = get_all_embeddings(g_max_c, H)
            
        #     print(f'there are {len(S)} embeddings of the max cc.')
            
        #     if len(S) == 0:
        #         # print('no embedding!')
        #         # print(S)
        #         return False, {}

        #     g_temp = nx.Graph()
        #     g_temp.add_edges_from(list(g.edges()))
        #     g_temp.remove_nodes_from(list(c_max))
            
        #     Examined_Images = []
        #     for m in S:
        #         # print(m)
        #         m_image_set = set(m.values()) 
        #         if m_image_set in Examined_Images:
        #             continue
                
        #         Examined_Images.append(m_image_set)
                

        #         H_temp = nx.Graph()
        #         H_temp.add_edges_from(list(H.edges()))
        #         H_temp.remove_nodes_from(list(m.values()))
                
        #         # embeddable, result = is_embeddable(g_temp, H_temp, stop, EXP)
        #         # if embeddable:
        #         #     print(f'We have matched {len(m+result)} nodes')
        #         #     return True, m+result
                
        #     return False, {}
        
        # else:
        #     # TODO: exploit graph center to anchor the embedding
        #     # print(nx.center(g))
        #     # print(nx.center(H))

        #     vf2 = Vf(g, H, {}, stop)
        #     result = vf2.dfsMatch({})
        #     if len(result) == lng:
        #         return True, result   
        #     return False, {}


def extract_circuit(filename, path, node_num):
    # compose the input Quantum Circuit
    q = QuantumRegister(node_num, 'q')
    cir_in = QuantumCircuit(q)
    cir_temp = cir_in.from_qasm_file(path+filename)
    cir_in.compose(cir_temp, inplace=True)
    if node_num < cir_temp.num_qubits:
        raise Exception("Cannot compose circuit!") 

    return cir_in

def graph_of_circuit(circuit):
    ''' Return the induced graph of the reduced circuit C
            - node set: qubits in C
            - edge set: all pair (p,q) if CNOT [p,q] or CNOT[q,p] in C
        Args:
            C (list): the input reduced circuit
        Returns:
            g (Graph)
    '''   
    g = nx.Graph()
    for gate in circuit:
        if gate.operation.name != 'cx': continue
        p, q = gate.qubits[0]._index, gate.qubits[1]._index
        g.add_edge(p,q)
    return g  

def get_all_isomorphisms(graph):
    from vfsexp import Vf
    """ We may include more parameters """

    vf2 = Vf(graph, graph, {}, 1000)
    S = vf2.dfsMatchAll([])
    return S    

def get_all_embeddings(g, H):
    from vfsexp import Vf

    vf2 = Vf(g, H, {}, 100)
    S = vf2.dfsMatchAll([])
    return S    

"""AG and Benchmarks"""

# AG = ag.qgrid(2,3)
# AG_name = 'G2x3'
# path = '../sabredepth/bench/6Qbench/'

# AG = ag.q20() 
# AG_name = 'Tokyo'

# path = '../sabredepth/bench/20Q_depth_Tokyo/'

# path = '../sabredepth/bench/qiskit_circuit_benchmark/'

# AG = ag.sycamore() 
# AG_name = 'Sycamore53Q'
# path = '../sabredepth/bench/53Q_depth_Sycamore/'

# path = '../sabredepth/bench/53Q_depth_Rochester/'
# AG = ag.rochester()
# AG_name = 'Rochester'


# result = get_all_isomorphisms(AG)
# print(len(result))

# if result:
#     for embedding in result:
#         print(embedding[0])
        
# AG_name = 'Sycamore54Q'

AG = ag.Sycamore54Q()
path = '../sabredepth/bench/BNTF/'

""" 54QBT_05CYC_QSE_3.qasm and 54QBT_10CYC_QSE_3.qasm are falsely detected as not embeddable if stop=10, 
    but both can be detected if stop=1000. The 5CYC one is harder as it is falsely detected when stop=500. 
    54QBT_05CYC_QSE_9.qasm is also falsely detected if stop=10 @23.05.17, but detected if stop=50; 
    so is 54QBT_10CYC_QSE_3.qasm
"""  

coupling_map = CouplingMap(couplinglist=AG.edges())

start = time.time()    
print(time.asctime())



# S = get_all_embeddings(AG, AG)
# for embedding in S:
#     print(embedding)

count = 0
count_t, count_f = 0, 0
for filename in os.listdir(path):
    if not filename.endswith('.qasm'): continue
    # if filename != '16QBT_40CYC_TFL_0.qasm': continue
    # if filename != '6QBT_large_depth_opt_1_2.55_no.8.qasm': continue
    # if filename != '54QBT_05CYC_QSE_3.qasm': continue
    if filename != '54QBT_05CYC_QSE_9.qasm': continue

    # if '54QBT' not in filename: continue
    # if '16QBT' not in filename: continue
    print(filename)

    '''Extract the circuit from qasm files'''
    circuit = extract_circuit(filename, path, coupling_map.size())
    # print(circuit.depth(), circuit.count_ops(), circuit.size())
    g = graph_of_circuit(circuit)
    t_start = time.time()
    t = is_embeddable(g,AG,100, EXP=True, CLEVER = True)
    finish = time.time()-t_start
    
    if not t[0]:
    # if not nx.is_connected(g) or not t[0]:
        print(filename,t[0], nx.is_connected(g))
        count += 1
    # if finish >= 1:
    #     count += 1
    #     print(filename, t[0], finish)
# 
end = time.time()
print('Used time (s):', count, count_f, count_t, round(end-start,2), time.asctime() )

