import networkx as nx
import time


class Vf:
  
    def dfsMatch(self, subgraph, graph, curMap, stop): #sl stop is the time limit
        # print('**'*len(curMap), '!dfsMatch called')
        # print(curMap)
        # TODO: is stop enforced correctly?
        start_A = time.time()

        if is_complete(curMap,subgraph):
            return curMap

        '''Construct the current neighborhoods of the mapping: v is the next-vertex-to-be-mapped 
            X1 the set of candidates in graph '''
        v, subMNeighbor, gMNeighbor, gNMNeighbor =  nxt_pairs(subgraph, graph, curMap)
        
        """ If we cannot find a correspondence for v then we backtrack """ 
        if (subMNeighbor and len(subMNeighbor) > len(gMNeighbor)) or not gNMNeighbor:
            return curMap

        # TODO: should subMNeighbor a subgraph of gMNeighbor? and 
        #  subMneighbor+curMap.subMap() a subgraph of gMneighbor+curMap.gMap()
        #  Make use of this fact and design an efficient algorithm 
        
        """Check if the subgraphs restricted to subMNeighbor and gMNeighbor are subgraph-isomorphic"""
        subgMN = subgraph.subgraph(subMNeighbor) 
        gMN = graph.subgraph(gMNeighbor)
        vf2 = Vf()
        temp = vf2.dfsMatch(subgMN, gMN, {}, 10)
        if temp == None or len(temp) < len(subgMN):
            return curMap
        
        for u in gNMNeighbor:

            if (isMeetRules(v, u, subgraph, graph, curMap, subMNeighbor, gMNeighbor)):

                curMap[v] = u
                
                if time.time()-start_A > stop: 
                    print('dfsmatch time exceeds', stop)
                    start_A = time.time() # reset start_A
                    return curMap
                
                curMap = self.dfsMatch(subgraph, graph, curMap, stop)

                if is_complete(curMap,subgraph):
                    """ A complete embedding is found """
                    return curMap
                
                """ The extension of curMap with {v:u} is failed."""
                curMap.pop(v)
        
        """ The extension of with {v: } failed. We backtrack and 
            consider the next candidate value of the previous key in curMap """ 
            
        # print('backtrack', curMap)
        
        # TODO: should we return curMap here?
        return curMap 

#sl divide the graph neighborhood of a vertex into two disjoint parts: pre (in map) and succ (not in map)
def preSucc(vNeighbor, uNeighbor, curMap):
    #vertexNeighbor and curMap can be empty
    
    vPre, vSucc, uPre, uSucc = [], [], [], []
    for vertex in vNeighbor:
        if vertex in curMap.keys():            
            vPre.append(vertex)
        else:
            vSucc.append(vertex)
       
    for vertex in uNeighbor:
        if vertex in curMap.values():            
            uPre.append(vertex)
        else:
            uSucc.append(vertex)

    return vPre, vSucc, uPre, uSucc

""" Verify if {v:u} can extend curMap """
def isMeetRules(v, u, subgraph, graph, curMap, subMNeighbor, gMNeighbor):
        
    if not curMap:
        return True     
    
    vNeighbor = list(nx.all_neighbors(subgraph, v))
    uNeighbor = list(nx.all_neighbors(graph, u))
            
    vPre, vSucc, uPre, uSucc = preSucc(vNeighbor, uNeighbor, curMap)
        
    ''' v cannot have more predecessors/successors than u'''
    if len(vPre) > len(uPre) or len(vSucc) > len(uSucc):
        return False
                   
    for pre in vPre:
        if curMap[pre] not in uPre:
            return False
    
    ''' v cannot have more successors that are map neighbours than u'''
    len1 = len(set(vNeighbor) & set(subMNeighbor)) #subMNeighborhood
    len2 = len(set(uNeighbor) & set(gMNeighbor))

    if len1 > len2:
        return False
    return True
    
    
def is_complete(curMap, subgraph):
    if len(curMap) == len(nx.nodes(subgraph)):
        return True
    return False

def nxt_pairs(subgraph, graph, curMap):
    '''Construct the current neighborhoods of the mapping'''

    subMNeighbor = [q  for x in curMap.keys() for q in nx.all_neighbors(subgraph,x)]
    subMNeighbor = list(set(subMNeighbor) - set(curMap.keys())) # unmapped neighbours in subgraph

    gMNeighbor = [q for x in curMap.values() for q in nx.all_neighbors(graph,x)]
    gMNeighbor = list(set(gMNeighbor) - set(curMap.values())) # unmapped neighbours in graph
    
    """ Select the next to-be-mapped node in subgraph and candidate nodes in graph. """ 
    X = subMNeighbor[:]
    gNMNeighbor = gMNeighbor[:]    

    if not subMNeighbor:

        """ If subgraph is connected then curMap should be empty """
        if nx.is_connected(subgraph) and len(curMap) > 0: 
            raise Exception ('The subgraph is disconnected!')

        X = list(set(nx.nodes(subgraph)) - set(curMap.keys()))            
        gNMNeighbor = list(set(nx.nodes(graph)) - set(curMap.values()))


    '''Rank the unmapped neighbors by their degrees'''    
    subNMN_deg = list([nx.degree(subgraph, v), v] for v in X)
    subNMN_deg.sort(key=lambda t: t[0], reverse=True)
    
    '''Select the node with the largest degree!'''
    v =  subNMN_deg[0][1] #sl the next subgraph node to be mapped 
    # print('__'*len(curMap), 'extend with node', v, curMap)

    '''Remove those graph neighbours which cannot match the suggraph candidate node''' 
    gNMNeighbor = [ t for t in gNMNeighbor if\
                   nx.degree(subgraph, v) <= nx.degree(graph,t)]
    
    return v, subMNeighbor, gMNeighbor, gNMNeighbor