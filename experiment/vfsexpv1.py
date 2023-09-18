""" Find an embedding which is close to a given mapping """ 

import networkx as nx
import time


class Vf:
    def __init__(self,
                subgraph: nx.Graph, 
                graph: nx.Graph,
                curMap: dict, 
                stop: int,
                cost=None, 
                preMap=None, 
                upperbound=None
                ):
       # internalizing initial parameters
       self.graph = graph
       self.subgraph = subgraph
       self.curMap = {}
       self.cost = cost
       self.preMap = preMap 
       self.stop = stop
       # self.rec_depth = 0
       self.upperbound = upperbound
  
    def dfsMatch(self): #sl stop is the time limit
        # print('**'*len(self.curMap), '!dfsMatch called')
        # print('**'*len(self.curMap), '!dfsMatch called', self.curMap)
        # TODO: is stop enforced correctly?
        start_A = time.time()

        if self.is_complete():
            # print('complete I')
            # print('complete I', self.curMap)
            return self.curMap

        '''Construct the current neighborhoods of the mapping: v is the next-vertex-to-be-mapped 
            X1 the set of candidates in self.graph '''

        nxt_vtx, subMNeighbor, gMNeighbor, gNMNeighbor = self.nxt_Candpairs()
        
        """ If we cannot find a correspondence for v then we backtrack """ 
        if (subMNeighbor and len(subMNeighbor) > len(gMNeighbor)) or not gNMNeighbor:
            # print('incomplete I', self.curMap, subMNeighbor, gMNeighbor, gNMNeighbor)
            return self.curMap

        # TODO: should subMNeighbor a self.subgraph of gMNeighbor? and 
        #  subMneighbor+curMap.subMap() a self.subgraph of gMneighbor+curMap.gMap()
        #  Make use of this fact and design an efficient algorithm 
        
        """Check if the self.subgraphs restricted to subMNeighbor and gMNeighbor are self.subgraph-isomorphic"""
        # subgMN = self.subgraph.subgraph(subMNeighbor) 
        # gMN = self.graph.subgraph(gMNeighbor)
        # vf2 = Vf(subgMN,gMN,{},10)
        # temp = vf2.dfsMatch()
        # if temp == None or len(temp) < len(subgMN):
        #     return self.curMap
        
        for u in gNMNeighbor:

            if self.CandpairMeetsRules(nxt_vtx, u, subMNeighbor, gMNeighbor):

                self.curMap[nxt_vtx] = u
                
                if time.time()-start_A > self.stop: 
                    # print('dfsmatch time exceeds', self.stop)
                    start_A = time.time() # reset start_A
                    return self.curMap
                
                self.dfsMatch()

                if self.is_complete():
                    """ A complete embedding is found """
                    # print('complete II', self.curMap)
                    # print('complete II')

                    return self.curMap
                
                """ The extension of curMap with {v:u} is failed."""
                self.curMap.pop(nxt_vtx)
                    
        
        """ The extension of with {v: } failed. We backtrack and 
            consider the next candidate value of the previous key in curMap """ 
            
        # print('__'*len(self.curMap), 'backtrack', self.curMap)
        # print('__'*len(self.curMap), 'backtrack')
        
        # TODO: should we return curMap here?
        return self.curMap 
    
    """ Verify if {v:u} can extend curMap """
    def CandpairMeetsRules(self, v, u, subMNeighbor, gMNeighbor):
            
        if not self.curMap:
            return True     
        
        vNeighbor = list(nx.all_neighbors(self.subgraph, v))
        uNeighbor = list(nx.all_neighbors(self.graph, u))
                
        vPre, vSucc = preSucc(vNeighbor, self.curMap.keys())
        uPre, uSucc = preSucc(uNeighbor, self.curMap.values())
            
        ''' v cannot have more predecessors/successors than u'''
        if len(vPre) > len(uPre) or len(vSucc) > len(uSucc):
            return False
                       
        for pre in vPre:
            if self.curMap[pre] not in uPre:
                return False
        
        ''' v cannot have more successors in curMap than u does'''
        len1 = len(set(vNeighbor) & set(subMNeighbor)) #subMNeighborhood
        len2 = len(set(uNeighbor) & set(gMNeighbor))

        if len1 > len2:
            return False
        return True
        
        
    def is_complete(self):
        if len(self.curMap) == len(nx.nodes(self.subgraph)):
            return True
        return False

    def nxt_Candpairs(self):
        '''Construct the current neighborhoods of the mapping'''

        subMNeighbor = getNeiborhood(self.subgraph, self.curMap.keys())
        gMNeighbor = getNeiborhood(self.graph, self.curMap.values()) # unmapped neighbours in self.graph
        
        """ Select the next to-be-mapped node in self.subgraph and candidate nodes in self.graph. """ 
        X = subMNeighbor[:]
        gNMNeighbor = gMNeighbor[:]    

        if not subMNeighbor:

            """ If self.subgraph is connected then curMap should be empty """
            if nx.is_connected(self.subgraph) and len(self.curMap) > 0: 
                raise Exception ('The self.subgraph is disconnected!')

            X = list(set(nx.nodes(self.subgraph)) - set(self.curMap.keys()))            
            gNMNeighbor = list(set(nx.nodes(self.graph)) - set(self.curMap.values()))

        # print(X, gNMNeighbor)

        '''Rank the unmapped neighbors by their degrees'''    
        subNMN_deg = list([nx.degree(self.subgraph, v), v] for v in X)
        subNMN_deg.sort(key=lambda t: t[0], reverse=True)
        
        '''Select the node with the largest degree!'''
        nxt_vtx =  subNMN_deg[0][1] #sl the next self.subgraph node to be mapped 

        '''Remove those self.graph neighbours which cannot match the suggraph candidate node''' 
        gNMNeighbor = [ t for t in gNMNeighbor if\
                       nx.degree(self.subgraph, nxt_vtx) <= nx.degree(self.graph,t)]
        
        return nxt_vtx, subMNeighbor, gMNeighbor, gNMNeighbor

#sl divide the graph neighborhood of a vertex into two disjoint parts: pre (in map) and succ (not in map)
def preSucc(Neighborhood, mapped_list):
    #vertexNeighbor and mapped_list can be empty
    
    Pre, Succ = [], []
    for vertex in Neighborhood:
        if vertex in mapped_list:            
            Pre.append(vertex)
        else:
            Succ.append(vertex)

    return Pre, Succ

def getNeiborhood(graph, mapped_list):
    Neighborhood = [q  for x in mapped_list for q in nx.all_neighbors(graph,x)]
    Neighborhood = list(set(Neighborhood) - set(mapped_list)) 
    return Neighborhood

def mapdist(map1, map2, subgraph, graph):
    distance = 0
    for p in subgraph.nodes():
        if p not in map1.keys(): continue
        if p not in map2.keys(): continue    
        distance += nx.shortest_path_length(graph, map1[p], map2[p])
    return distance
        
    