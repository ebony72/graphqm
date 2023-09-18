#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# import qiskit
# print(qiskit.__qiskit_version__)
    
from qiskit.transpiler import CouplingMap
from qiskit import QuantumCircuit, QuantumRegister
# from vfs230503 import Vf
from vfs import Vf
# from vfsexpand3 import Vf

import ag,time,os

import networkx as nx
# from qiskit.tools.parallel import CPU_COUNT
# print('CPU Count: ', CPU_COUNT)

def is_embeddable(g, H, stop):
    '''check if a small graph g is embeddable in a large H, anchor is bool
        g, H (Graph)
        anchor (bool): whether or not mapping anchor of g to that of H
        stop (float): time limit for vf2
    '''
    
    # #vfs_li
    # result = {} 
    # vf2 = Vf(g, H, result, stop)
    # result = vf2.dfsMatch(result)
    
    vf2 = Vf()
    result = vf2.dfsMatch(g, H, {}, stop)

    lng = len(nx.nodes(g))
    if result != None and len(result) == lng:
        return True, result   
    return False, result


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



"""AG and Benchmarks"""

# AG = ag.qgrid(2,3)
#AG_name = 'G2x3'
# path = '../sabredepth/bench/6Qbench/'

# AG = ag.q20() 
#AG_name = 'Tokyo'

# path = '../sabredepth/bench/20Q_depth_Tokyo/'

# path = '../sabredepth/bench/qiskit_circuit_benchmark/'

# AG = ag.sycamore() 
# AG_name = 'Sycamore53Q'
# path = '../sabredepth/bench/53Q_depth_Sycamore/'

path = '../sabredepth/bench/53Q_depth_Rochester/'
#AG = ag.rochester()
# AG_name = 'Rochester'

AG = ag.Sycamore54Q()
# AG_name = 'Sycamore54Q'
# path = '../sabredepth/bench/BNTF/'



coupling_map = CouplingMap(couplinglist=AG.edges())

start = time.time()    
print(time.asctime())


count = 0
for filename in os.listdir(path):
    if not filename.endswith('.qasm'): continue
    # if filename != '53QBT_depth_Rochester_small_opt_2_2.55_no.9.qasm': continue
    # if filename != '6QBT_large_gate_opt1_15_1.5_no.5.qasm': continue
    # if filename != '54QBT_05CYC_QSE_3.qasm': continue
    print(filename)

    '''Extract the circuit from qasm files'''
    circuit = extract_circuit(filename, path, coupling_map.size())
    # print(circuit.depth(), circuit.count_ops(), circuit.size())
    g = graph_of_circuit(circuit)
    
    if is_embeddable(g,AG,10)[0]:
        print('embeddable!')
        count += 1
        # print(filename)

end = time.time()
print('Used time (s):', count, round(end-start,2), time.asctime() )

