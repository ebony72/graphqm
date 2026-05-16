from collections import defaultdict
import copy
from qiskit import QuantumCircuit, QuantumRegister
from qiskit.dagcircuit import DAGCircuit, DAGOpNode, DAGInNode, DAGOutNode
from qiskit.converters import circuit_to_dag, dag_to_circuit
from qiskit.transpiler.layout import Layout
from qiskit.circuit.quantumregister import Qubit
from qiskit.visualization import dag_drawer
from qiskit.qasm import Qasm

import matplotlib.pyplot as plt
import networkx as nx
import rustworkx as rx

from vfsexp import Vf


""" From a QuantumCircuit, remove all 1qb gates and any 2qb gate [p,q] that has a parent [p,q] or [q,p]"""
def remove_1q_and_consecutive_2q_gates_in_circuit(circuit):
    
    qubit_set = set()
    for instruction in circuit:
        if len(instruction.qubits) != 2: continue
        if instruction.operation.name == 'cx': # only consider cx gates
            p, q = instruction.qubits[0]._index, instruction.qubits[1]._index
            qubit_set = qubit_set | {p,q}
    
    newcirc = QuantumCircuit(len(qubit_set))
    #newcirc = QuantumCircuit(circuit.num_qubits)
    record = [] #the current end layer of the reduced circuit
    for instruction in circuit:
        if len(instruction.qubits) != 2: continue
        if instruction.operation.name == 'cx': # only consider cx gates
            p, q = instruction.qubits[0]._index, instruction.qubits[1]._index
            if [p,q] in record or [q,p] in record:
                continue
            for x in record:
                if p in x or q in x:
                    record.remove(x)
            record.append([p,q])            
            newcirc.cx(p,q)
    return newcirc

def get_interaction_graph(dag: DAGCircuit):
    g = nx.Graph()
    qubit_layers = defaultdict(list)
    edge_layers = defaultdict(list)

    for layer_no, layer in enumerate(dag.layers()):
        #print(f"layer number{layer_no} {layer['partition']}")
        #if layer_no == 0: continue
        for qubit_pair in layer['partition']:
            p, q = qubit_pair[0]._index, qubit_pair[1]._index
            g.add_edge(p,q)
            qubit_layers[p].append(layer_no)
            qubit_layers[q].append(layer_no)
            edge_layers[(p,q)].append(layer_no)
            edge_layers[(q,p)].append(layer_no)

    for node, layers in qubit_layers.items():
        g.nodes[node]['layer_distribution'] = layers

    for edge, layers in edge_layers.items():
        g.edges[edge]['layer_distribution'] = layers
    return g

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

def has_cycle_3(graph):
    for u in graph.nodes():
        for v in graph.neighbors(u):
            for w in graph.neighbors(v):
                if u != w and graph.has_edge(u, w):
                    return True
    return False

def fast_no_embedding(subgraph, graph):
    # for AG with no 3-cycle
    if has_cycle_3(subgraph) and not has_cycle_3(graph): 
        return True
    
    subgraph_deg = list(nx.degree(subgraph, v) for v in subgraph.nodes())
    subgraph_deg.sort(reverse=True)

    graph_deg = list(nx.degree(graph, v) for v in graph.nodes())
    graph_deg.sort(reverse=True)
    
    l = len(subgraph_deg)
    for idx in range(l):
        if subgraph_deg[idx] > graph_deg[idx]:
            return True
        
    return False

def is_rx_embeddable(circuit, rxAG):
    """circuit is a DAGCircuit or a QuantumCircuit """
    if isinstance(circuit, DAGCircuit):
        qc = dag_to_circuit(circuit)
        g = graph_of_circuit(qc)

    if isinstance(circuit, QuantumCircuit):
        qc = remove_1q_and_consecutive_2q_gates_in_circuit(circuit)
        g = graph_of_circuit(qc)
        
    if isinstance(circuit, nx.Graph):
        g = copy.deepcopy(circuit)
    
    rxg = rx.networkx_converter(g)
        
    is_embeddable = rx.is_subgraph_isomorphic(rxAG, rxg, induced=False)
    if is_embeddable:
        vf2_map = rx.vf2_mapping(rxAG, rxg, subgraph=True, induced=False)
        #print(f"rx-vf2_mapping: {next(vf2_map)}")
        return is_embeddable, vf2_map
    return is_embeddable, None

def is_embeddable(g, H, stop):
    '''check if a small graph g is embeddable in a large H, anchor is bool
        g, H (Graph)
        stop (float): time limit for vf2
    '''
    if fast_no_embedding(g, H):
        return False, {}
    
    lng = len(nx.nodes(g))
        
    new_g = g.copy()
    #print(len(new_g.edges()) == len(g.edges()))

    new_H = H.copy()
    #temp_map = dict()

    vf2 = Vf(new_g, new_H, {}, stop)
    result = vf2.dfsMatch({})
    if len(result) == lng:
        #print('emb', result)
        #return True, temp_map.update(result)  
        return True, result
    return False, {}

def draw_nx_graph(g):
    if isinstance(g, DAGCircuit): 
        qc = dag_to_circuit(g)
        g = graph_of_circuit(qc)
    
    if not isinstance(g, nx.Graph):
        raise Exception('g should be a nx.Graph')
        
    # Create a layout for the nodes
    pos = nx.spring_layout(g) #sl !!not sure if this is the correct layout for us!!

    # Draw the nodes and edges
    nx.draw(g, pos, with_labels=True, node_color='skyblue', node_size=500, font_size=12, font_color='black')

    # Display the graph
    plt.show()
    
def _successors(node, dag):
    for _, successor, edge_data in dag.edges(node):
        if not isinstance(successor, DAGOpNode):
            continue
        #"""Our dag is derived from special circuit with 1q gates and 2q consecutive identical gates removed."""
        #if isinstance(node, DAGOpNode) and successor.qargs == node.qargs: 
        #    continue #sl sometimes successor and node are identical, don't know why
        if isinstance(edge_data, Qubit):
            yield successor

"""Partition a dagCircuit into sections s.t. each section is embeddable into a given architecture""" 

def partition(dag, architecture, method='greedy'):
    """dag:DAGCircuit satisfies
         (i) it contains no single-qubit gates; and 
        (ii) any two consecutive cx gates should have act on disjoint or partially overlapping qubits
    """
    print(f'The dagCircuit has {dag.count_ops()} cx gates')
    for node in dag.nodes():
        if not isinstance(node, DAGOpNode): continue
        if len(node.qargs) != 2 or node.op.name != 'cx': 
            raise Exception(f'check why dag still has single-qubit gates {type(node), node.op.name}')
    
    """Use applied_predecessors to track gates which are ready to process, i.e., can be put in front layer"""
    # Create a defaultdict with a default value of 0
    applied_predecessors = defaultdict(int)
    for _, input_node in dag.input_map.items(): 
        for successor in _successors(input_node, dag):
            applied_predecessors[successor] += 1

    
    step = 0
    processed_node = []
    num_part = 0
    part_list = []
    current_part_dag = dag.copy_empty_like()
    part_graph = nx.Graph()

    # generate the current layer and examine for each node of the current layer
    front_layer = dag.front_layer()
    while front_layer:
        step += 1
        
        """Put cx gate in front_layer to the current section whenever possible"""
        execute_gate_list = []        
        for node in front_layer:            
            v0, v1 = node.qargs
            
            EMBEDDABLE = True
            if (v0._index,v1._index) not in part_graph.edges():
                temp_graph = copy.deepcopy(part_graph)
                temp_graph.add_edge(v0._index,v1._index)      
                EMBEDDABLE = is_embeddable(temp_graph, architecture, stop=10)[0]
                
            if EMBEDDABLE:
                execute_gate_list.append(node)
                processed_node.append(node)
                current_part_dag.apply_operation_back(node.op, node.qargs, node.cargs)
                part_graph.add_edge(v0._index,v1._index)      

        """The whole layer has been examined!"""
        if execute_gate_list: 
            """Update the front layer!"""
            for node in execute_gate_list:
                front_layer.remove(node)
                for successor in _successors(node, dag):
                    applied_predecessors[successor] += 1
                    if applied_predecessors[successor] == len(node.qargs):
                        front_layer.append(successor)
            
        else: 
            """No gate in front_layer can be added. A new section should start!"""
            part_list.append(current_part_dag)
            num_part += 1

            print(f'step {step}: Section {num_part} constructed!')
            #print([(node.qargs[0]._index, node.qargs[1]._index) for node\
            #       in current_part_dag.topological_op_nodes() if isinstance(node, DAGOpNode)])
            
            #draw_nx_graph(part_graph)

            """Start a new part dag!"""
            current_part_dag = dag.copy_empty_like()
            part_graph = nx.Graph()
            #print(f'step {step}: start a new part dag {current_part_dag.count_ops()}')
    
    """The final part dag"""
    part_list.append(current_part_dag)
    num_part += 1

    #print(f'step {step}: Section {num_part} constructed!')
    #print([(node.qargs[0]._index, node.qargs[1]._index) for node\
    #       in current_part_dag.topological_op_nodes() if isinstance(node, DAGOpNode)])

    #draw_nx_graph(part_graph)

    if len(processed_node) < dag.count_ops()['cx']:
        raise Exception (f'The partition is incomplete! {len(processed_node), dag.count_ops()}')
        
    #print(f'{len(processed_node)} cx gates have been processed.')

    print(f'The partition is complete and we have {num_part} sections!')
    return part_list

def has_descendnent(node, dag):
    return [s for s in _successors(node, dag) if isinstance(s,DAGOpNode)]

def realign(dag1, dag2):
    
    qc2 =  dag_to_circuit(dag2)
    graph2 = graph_of_circuit(qc2)  
    nodes_in_reverse_topological_order = list(reversed(list(dag1.topological_op_nodes())))

    for node in nodes_in_reverse_topological_order:
        if not isinstance(node, DAGOpNode) or has_descendnent(node, dag1): continue
        if (node.qargs[0]._index, node.qargs[1]._index) in graph2.edges():
            dag1.remove_op_node(node)
            dag2.apply_operation_front(node.op, node.qargs, node.cargs)
    return dag1, dag2

"""Consider reduced QuantumCircuit"""
def graph_profile(qc: QuantumCircuit, printOK=False):

    #qc should be reduced first!
    redqc = remove_1q_and_consecutive_2q_gates_in_circuit(qc)
    dag = circuit_to_dag(redqc)

    ig = get_interaction_graph(dag)
    if printOK: 
        print(f'The DAGCircuit has {dag.num_qubits()} qubits, depth {dag.depth()}, {dag.count_ops()}')
    
    Node_Layer = dict()
    if printOK: 
        print('~~~~~~~~~~~~~~~~~~~~~~~~')                                 
        print('*node distribution*')
        print('~~~~~~~~~~~~~~~~~~~~~~~~')                                 
    for node in ig.nodes():
        if printOK: 
            print(node, ig.nodes[node]['layer_distribution'])
        Node_Layer[node] = ig.nodes[node]['layer_distribution']
    
    Edge_Layer = dict()
    if printOK:
        print('========================')                                 
        print('*edge distribution*')
        print('========================')                                 
    for edge in ig.edges():
        if printOK:
            print(edge, ig.edges[edge]['layer_distribution'])
        Edge_Layer[edge] = ig.edges[edge]['layer_distribution']
        
    if printOK: 
        # Draw the graph
        pos = nx.spring_layout(ig)  # Define the layout (you can choose other layouts)
        nx.draw(ig, pos, with_labels=True, node_size=500, node_color='skyblue', font_size=20)
        plt.show()  # Display the graph
    
    return ig, Node_Layer, Edge_Layer

#TODO: the following functions require revision: we could differ betwen all_left, all_right, and the single_layer cutting points
# a layer i is a single_layer cutting point if for any edge with min(Edge_Layer[edge]) <= i <= max(Edge_Layer[edge]), we have 
# Edge_Layer[edge] = i; i is an all_left cutting point if for any above edges, we have i = max(Edge_Layer[edge]).
def cutting_point(i, selected_edges, Edge_Layer, ig):
    """layer i a cutting point w.r.t. edges in EX 
            if for each edge e out of EX, its distribution is either all before i or all after i """
    edge_list = [edge for edge in ig.edges() if edge not in selected_edges and min(Edge_Layer[edge]) <= i <= max(Edge_Layer[edge])] 
    if not edge_list: 
        return True
    some_left = False
    some_right = False
    for edge in edge_list:
        if min(Edge_Layer[edge]) < i < max(Edge_Layer[edge]): 
            return False
        if i == min(Edge_Layer[edge]) < max(Edge_Layer[edge]): 
             some_right = True
        if min(Edge_Layer[edge]) < i == max(Edge_Layer[edge]): 
            some_left = True
    if some_left and some_right:
        return False
    return True

def all_cutting_points(selected_edges, Edge_Layer, depth, ig):
    
    cutting_list = [i for i in range(depth) if cutting_point(i, selected_edges, Edge_Layer, ig)]
    return cutting_list

"""Calculate the cutting points and compute the graph of each section"""
def dynamic_graph_partition(qc, lev=1):
    newcirc = remove_1q_and_consecutive_2q_gates_in_circuit(qc)
    dag = circuit_to_dag(newcirc)
    print(f'orginal circuit info: {dag.count_ops(), dag.depth()}')
    g, _, Edge_Layer = graph_profile(newcirc, True)

    if lev != 1:
        raise Exception ('We currently only consider the level 1 case.')
        
    selected_edges = []
    cutting_list = all_cutting_points(selected_edges, Edge_Layer, dag.depth(), g)
    cutting_list.sort()
    print(f'The cutting points are {cutting_list}')
    
    if not cutting_list:
        return [g]
    
    """show the graph of each section"""
    GRAPHS = []
    for idx in range(len(cutting_list)+1):
        "determine the section corresponding to each idx"
        if idx == 0: #the first section
            LayerList = list(range(cutting_list[0]+1))
        elif idx == len(cutting_list): #the last section
            LayerList = list(range(cutting_list[-1], dag.depth()))
            #print(f'the end {cutting_list[-1], LayerList}')            
        else:
            LayerList = list(range(cutting_list[idx-1]+1, cutting_list[idx]+1))
            
        print(f"section {idx}: {LayerList}")                     
        edgelist = [edge for edge in g.edges() if set(Edge_Layer[edge])&set(LayerList)]
        newgraph = nx.Graph()
        newgraph.add_edges_from(edgelist)
        draw_nx_graph(newgraph)
        GRAPHS.append(newgraph)           
    return GRAPHS
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
#_________________TEST_____________________________________________________________#
if __name__=='__main__':
    from ag import qgrid, q20
    import time
    import os

    """Divide-and-Conquer works fine on Tokyo and phase_estimation, phase_oracle, AND, OR, """
    path = '../bench/qiskit_circuit_benchmark/' 
    filename = 'excitation_preserving_6.qasm'
    #filename = 'grover_operator_10.qasm'
    #filename = 'and_5.qasm'

    #AG = qgrid(2,3)
    AG = q20()

    with open(path+filename, 'r') as file:
        qasm_code = file.read()

    # Create a QuantumCircuit from the QASM code
    qc = QuantumCircuit.from_qasm_str(qasm_code)
    print(qc.count_ops())

    newcirc = remove_1q_and_consecutive_2q_gates_in_circuit(qc)

    dag = circuit_to_dag(newcirc)
    print(dag.count_ops())
    
    X = partition(dag, AG, method='greedy')
    
    W = copy.deepcopy(X)
    for i in range(1, len(W)-1): #start from 1 since we don't want or need to weak X[0]
        W[i], W[i+1] = realign(W[i], W[i+1])

    for i in range(len(X)):
        print(f'step {i} of {len(X)}. {X[i].count_ops(),W[i].count_ops()}')

    print(sum([X[i].count_ops()['cx'] for i in range(len(X))]))
    print(sum([W[i].count_ops()['cx'] for i in range(len(W))]))

    for i in range(len(W)):
        print(f'Modified Section {i} has CX gates')
        print([(node.qargs[0]._index, node.qargs[1]._index) for node\
               in W[i].topological_op_nodes() if isinstance(node, DAGOpNode)])
        draw_nx_graph(W[i])