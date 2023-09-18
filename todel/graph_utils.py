'''Created on  2022.03.03 by Sanjiang Li || mrlisj@gmail.com '''

import networkx as nx


spl = nx.shortest_path_length
def SPL(g):
    if not nx.is_connected(g): raise Exception ('g is not connected!')
        # '''g is disconnected! We consider its largest connected component instead!'''
        # largest_cc = max(nx.connected_components(g), key=len)
        # g = g.subgraph(largest_cc)
    spl_dic = dict() 
    V = list(g.nodes())
    V.sort()
    for p in V:
        for q in V:
            if (q,p) in spl_dic:
                d = spl_dic[(q,p)]
            else:
                d = nx.shortest_path_length(g,p,q)
            spl_dic[(p,q)] = d
    return spl_dic

def centre(g):
    if not nx.is_connected(g): 
        largest_cc = max(nx.connected_components(g), key=len)
        g = g.subgraph(largest_cc).copy() 

    radium = nx.diameter(g)
    Centre = []
    for node in g.nodes():
        radium_temp = max([spl(g,node,nodex) for nodex in g.nodes])
        if  radium_temp > radium: continue
        radium = radium_temp
        Centre.append([node,radium])
    Centre = [cand[0] for cand in Centre if cand[1] == radium ]
    #deg = max([g.degree(node) for node in Centre ])
    step = 0
    while len(Centre) > 1 and step < radium:
        step += 1
        '''Compare how many (step+1)-nbrs they have if they have the same (step)-nbrs'''
        Centre = [[x, len([y for y in g.nodes() if spl(g,x,y)== step+1])] for x in Centre]
        max_val = max([item[1] for item in Centre])
        Centre = [item[0] for item in Centre if item[1]==max_val]
    return Centre[0]  

def hub(g):
    '''A hub of g is a node with maximum degree'''
    if not nx.is_connected(g): 
        largest_cc = max(nx.connected_components(g), key=len)
        g = g.subgraph(largest_cc).copy() 
        
    deg = max([g.degree(node) for node in g.nodes ])
    Hub = []
    for node in g.nodes():
        if g.degree(node) == deg: Hub.append(node)

    step = 0
    while len(Hub) > 1 and step < nx.diameter(g):
        step += 1
        Hub = [[x, len([y for y in g.nodes() if spl(g,x,y)== step+1])] for x in Hub]
        max_val = max([item[1] for item in Hub])
        Hub = [item[0] for item in Hub if item[1]==max_val]
    return Hub[0]

#------------------------------------------------------------------------#
def map_dist(subgraph, graph, tau_dict1, tau_dict2):
    dist = 0
    X = set(tau_dict1) & set(tau_dict2)
    for v in X:
        dist += spl(graph, tau_dict1[v], tau_dict2[v])
    return dist

#------------------------------------------------------------------------#
def is_embedding(tau_dict, subgraph, graph):
    '''Check if result is indeed an embedding'''
    for edge in nx.edges(subgraph):
        i, j = edge
        if i not in tau_dict or j not in tau_dict: continue
        if (tau_dict[i],tau_dict[j]) not in nx.edges(graph):
            # print(result, 'is not an embedding')
            return False
    return True

""" Return gate information 
    - for each gate, which layer it is in and how many steps left
"""
from qiskit.dagcircuit.dagnode import DAGOutNode

def get_layer_info(dag):
    layer_id = 0
    layer_dic = {} # layer_id : gates in this layer
    node_layer_dic = {} # node : layer_id
    for layer in dag.multigraph_layers():
        des = []    
        for x in layer:
            des.append(x._node_id)
            node_layer_dic[x] = layer_id
        layer_dic[layer_id] = des
        layer_id += 1
    
    node_expection = {}
    examined_node = []
    
    #sort DAGOutNode
    OutNodes = [ (outnode, node_layer_dic[outnode]) for outnode in dag.output_map.values()]
    OutNodes.sort(key = lambda x:  x[1], reverse=True)
    
    for outnode, depth in OutNodes:
        # print('outnode layer', outnode._node_id, node_layer_dic[outnode._node_id], dag.depth())
        for x in dag.ancestors(outnode):
            if x in node_expection: continue
            node_expection[x] = depth - node_layer_dic[x] # the rest steps after this node 
            examined_node.append(x._node_id)
            
    S = set(x._node_id for x in dag.nodes() if not isinstance(x, DAGOutNode))    
    if S != set(examined_node):
        raise Exception('Layer info error')
                           
    return layer_dic, node_layer_dic, node_expection