""" Find an embedding which is close to a given mapping """ 

import networkx as nx
import copy
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
       # initial parameters
       self.graph = graph
       self.subgraph = subgraph
       self.curMap = {} # we can also start with a partial map
       
       # terminate the search earlier when time limit is reached
       self.start = time.time()
       self.stop = stop
       
       # Find the mapping that is closest to the preMap
       # self.cost = cost
       self.preMap = preMap 
       # self.last_bestMap = None
       self.upperbound = upperbound
       # self.result = []

       # precompute immutable graph data for speed
       self._sub_nodes = list(self.subgraph.nodes())
       self._graph_nodes = list(self.graph.nodes())
       self._sub_deg = {v: self.subgraph.degree(v) for v in self._sub_nodes}
       self._graph_deg = {v: self.graph.degree(v) for v in self._graph_nodes}
       self._sub_neighbors = {v: list(self.subgraph.neighbors(v)) for v in self._sub_nodes}
       self._graph_neighbors = {v: list(self.graph.neighbors(v)) for v in self._graph_nodes}
       self._sub_maxdeg = max(self._sub_deg.values()) if self._sub_deg else 0
  
    def dfsMatch(self, S): 
        """ S is the result to return. 
            In this method, it is either empty or the first complete map """ 

        # TODO: do we need S in this method?
        
        # print('**'*len(self.curMap), '!dfsMatch called')
        # print('**'*len(self.curMap), '!dfsMatch called', self.curMap)

        if self.is_complete():
            # print('The first complete map is found! \n', self.curMap)
            S = copy.copy(self.curMap)
            return S

        # TODO: is stop enforced correctly?
        # if time.time()-self.start > self.stop: 
        #     # print('dfsmatch time exceeds', self.stop)
        #     return S

        '''Construct the current neighborhoods of the mapping: v is the next-vertex-to-be-mapped 
            X1 the set of candidates in self.graph '''

        nxt_vtx, subMNeighbor, gMNeighbor, gNMNeighbor = self.nxt_CandPairs()
        
        """ If we cannot find a correspondence for v then we backtrack """ 
        if (subMNeighbor and len(subMNeighbor) > len(gMNeighbor)) or not gNMNeighbor:
            # print('__'*len(self.curMap), 'End dfsMatch - I!', self.curMap, 'This branch failed!')
            return S
        
        mapped_sub = set(self.curMap.keys())
        mapped_g = set(self.curMap.values())
        for key in self.curMap:
            deg1 = outdegree_cached(key, self._sub_neighbors, mapped_sub)
            deg2 = outdegree_cached(self.curMap[key], self._graph_neighbors, mapped_g)

            if deg1 >  deg2:
                # print(deg1, deg2)
                return S
        
        for u in gNMNeighbor:
            if self.CandpairMeetsRules(nxt_vtx, u, subMNeighbor, gMNeighbor):

                """ Extend curMap with the candidate pair """
                self.curMap[nxt_vtx] = u
                
                S = self.dfsMatch(S)
                
                """ The extension of curMap with {v:u} is failed."""
                self.curMap.pop(nxt_vtx)
                # print('__'*len(self.curMap), 'This extension failed and we consider the next candidate', self.curMap)
                    
        
        """ The call of dfsMatch (with the current map) is failed. """ 
        
        # print('__'*len(self.curMap), 'End dfsMatch!', self.curMap)
        return S
    
    """ Return the mapping which has minimal distance with preMap """ 
    def dfsMatchBest(self, S): 
        """ S is the current result. 
            In this method, it is at first empty {} and then the current best complete map. """ 
            
        if self.is_complete():

            if self.upperbound and self.mapdist() >= self.upperbound:
                    return S

            self.upperbound = self.mapdist()
            S = copy.copy(self.curMap)
            
            return S

        if time.time() - self.start > self.stop: 
            return S

        '''Construct the current neighborhoods of the mapping: v is the next-vertex-to-be-mapped 
            X1 the set of candidates in self.graph '''

        nxt_vtx, subMNeighbor, gMNeighbor, gNMNeighbor = self.nxt_CandPairs()
        
        """ If we cannot find a correspondence for v then we backtrack """ 
        if (subMNeighbor and len(subMNeighbor) > len(gMNeighbor)) or not gNMNeighbor:
            return S
        
        for u in gNMNeighbor:
            if self.CandpairMeetsRules(nxt_vtx, u, subMNeighbor, gMNeighbor):

                self.curMap[nxt_vtx] = u
                
                if self.upperbound and self.preMap and self.mapdist() >= self.upperbound:
                    self.curMap.pop(nxt_vtx)
                    continue
                    
                S = self.dfsMatchBest(S)
                
                """ We consider the next candidate."""
                self.curMap.pop(nxt_vtx)
                          
        """ We backtrack and 
            consider the next candidate value of the previous key in curMap """ 
            
        return S 

    """ Return the mapping which has minimal distance with preMap """ 
    def dfsMatchAll(self, S):
        """ S is the current result. 
            In this method, it is at first empty and then the set if complete maps found so far. """ 
        # print('__'*len(self.curMap), 'Call dfsMatch', self.curMap, len(S))

        if self.is_complete():
            # print('__'*len(self.curMap), 'End dfsMatch!', '\n' f'Embedding {len(S)+1} found! \n', self.curMap)
            
            # self.curMap changes dynamically with search even if we put it in a list S.
            one_solution =  copy.copy(self.curMap)
            S.append(one_solution) 
            return S

        '''Construct the current neighborhoods of the mapping: v is the next-vertex-to-be-mapped 
            X1 the set of candidates in self.graph '''

        nxt_vtx, subMNeighbor, gMNeighbor, gNMNeighbor = self.nxt_CandPairs()
        
        """ If we cannot find a correspondence for v then we backtrack """ 
        if (subMNeighbor and len(subMNeighbor) > len(gMNeighbor)) or not gNMNeighbor:
            
            # print('__'*len(self.curMap), 'End dfsMatch!', self.curMap, 'This branch failed!', len(S))

            return S
        
        for u in gNMNeighbor:
            if self.CandpairMeetsRules(nxt_vtx, u, subMNeighbor, gMNeighbor):

                self.curMap[nxt_vtx] = u
                
                S = self.dfsMatchAll(S)
                
                """ The extension of curMap with {nxt_vtx:u} is failed."""
                self.curMap.pop(nxt_vtx)
                # print('__'*len(self.curMap), 'Backtrack', self.curMap, len(S))
                    
        
        """ The extension of with {nxt_vtx: } failed. We backtrack and 
            consider the next candidate value of the previous key in curMap """ 
        
        # print('__'*len(self.curMap), 'End dfsMatch!', self.curMap, len(S))
        return S
    
    """ Verify if {v:u} can extend curMap """
    def CandpairMeetsRules(self, v, u, subMNeighbor, gMNeighbor):
            
        if not self.curMap:
            return True     
        
        vNeighbor = self._sub_neighbors[v]
        uNeighbor = self._graph_neighbors[u]
                
        vPre, vSucc = preSucc(vNeighbor, self.curMap.keys())
        uPre, uSucc = preSucc(uNeighbor, self.curMap.values())
            
        ''' v cannot have more predecessors/successors than u'''
        if len(vPre) > len(uPre) or len(vSucc) > len(uSucc):
            return False
                       
        for pre in vPre:
            if self.curMap[pre] not in uPre:
                return False
        
        ''' v cannot have more successors in curMap than u does'''
        subMNeighbor_set = set(subMNeighbor)
        gMNeighbor_set = set(gMNeighbor)
        len1 = len(set(vNeighbor) & subMNeighbor_set) # subMNeighborhood
        len2 = len(set(uNeighbor) & gMNeighbor_set)

        if len1 > len2:
            return False
        return True
        
        
    def is_complete(self):
        if len(self.curMap) == len(self._sub_nodes):
            return True
        return False

    def nxt_CandPairs(self):
        '''Construct the current neighborhoods of the mapping'''
        
        # print('u', self.curMap)
        # print('me', self.preMap)
        subMNeighbor = getNeiborhood_cached(self._sub_neighbors, self.curMap.keys())
        gMNeighbor = getNeiborhood_cached(self._graph_neighbors, self.curMap.values()) # unmapped neighbours in self.graph
        
        """ Select the next to-be-mapped node in self.subgraph and candidate nodes in self.graph. """ 
        X = subMNeighbor[:]
        gNMNeighbor = gMNeighbor[:]    

        if not subMNeighbor:

            """ If the subgraph is connected then curMap should be empty """
            if nx.is_connected(self.subgraph) and len(self.curMap) > 0: 
                raise Exception ('The subgraph is disconnected!')

            X = list(set(self._sub_nodes) - set(self.curMap.keys()))
            
            subg_temp = self.subgraph.subgraph(X)
            X = max(nx.connected_components(subg_temp), key=len)
            
            gNMNeighbor = list(set(self._graph_nodes) - set(self.curMap.values()))

        # print(X, gNMNeighbor)

        """ Vf2++ rank vtx according to #(their neigbours in curMap), but it seems do not help. """
        # num_most_nghbrs = max([len(preSucc(list(nx.all_neighbors(self.subgraph, v)), self.curMap.keys())) for v in X])
        # X = [v for v in X if len(preSucc(list(nx.all_neighbors(self.subgraph, v)), self.curMap.keys())) == num_most_nghbrs]        
        
        '''Rank the unmapped neighbors by their degrees'''    
        # max_deg = max([nx.degree(self.subgraph, v) for v in X])
        max_deg = max(self._conn(v) for v in X)
        
 
        '''Select the node with the largest degree!'''
        # nxt_vtx = [v for v in X if nx.degree(self.subgraph, v) ==  max_deg][0] #sl the next self.subgraph node to be mapped 
        nxt_vtx = [v for v in X if self._conn(v) ==  max_deg][0] #sl the next self.subgraph node to be mapped 

        '''Remove those self.graph neighbours which cannot match the suggraph candidate node''' 
        nxt_deg = self._sub_deg[nxt_vtx]
        gNMNeighbor = [t for t in gNMNeighbor if nxt_deg <= self._graph_deg[t]]
            
        """ Rank nonmapped neighbours by distance to previous mapped node """
        if self.preMap:
            gNMN_deg = [[nx.shortest_path_length(self.graph, self.preMap[nxt_vtx], v), v] for v in gNMNeighbor]
        else:
            gNMN_deg = [[self._graph_deg[v], v] for v in gNMNeighbor]
            
        gNMN_deg.sort(key=lambda t: t[0])
        gNMNeighbor = [t[1] for t in gNMN_deg]
        return nxt_vtx, subMNeighbor, gMNeighbor, gNMNeighbor
    
    def mapdist(self):
        distance = 0
        for p in self.subgraph.nodes():
            if p not in self.preMap.keys(): continue
            if p not in self.curMap.keys(): continue    
            distance += nx.shortest_path_length(self.graph, self.preMap[p], self.curMap[p])
        return distance

    def _conn(self, v):
        return self._sub_deg[v] / self._sub_maxdeg \
                    + len(set(self._sub_neighbors[v]).intersection(set(self.curMap.keys())))
#sl divide the neighborhood of a vertex into two disjoint parts: pre (in map) and succ (not in map)
def preSucc(Neighborhood, mapped_list):
    #vertexNeighbor and mapped_list can be empty
    
    Pre, Succ = [], []
    for vertex in Neighborhood:
        if vertex in mapped_list:            
            Pre.append(vertex)
        else:
            Succ.append(vertex)

    return Pre, Succ

def getNeiborhood(g, mapped_list):
    """Get non-mapped neighbours of curMap
        mapped_list: curMap.keys() or curMap.values()
        g: subgraph or graph
    """
    # print(mapped_list)
    Neighborhood = [q  for x in mapped_list for q in nx.all_neighbors(g,x)]
    Neighborhood = list(set(Neighborhood) - set(mapped_list)) 
    return Neighborhood

def outdegree(v, g, mapped_list):
    return len([q for q in nx.all_neighbors(g,v) if q not in mapped_list])

def getNeiborhood_cached(neighbors_map, mapped_list):
    """Get non-mapped neighbors using a precomputed neighbor map."""
    mapped_set = set(mapped_list)
    Neighborhood = [q for x in mapped_set for q in neighbors_map[x]]
    return list(set(Neighborhood) - mapped_set)

def outdegree_cached(v, neighbors_map, mapped_set):
    return sum(1 for q in neighbors_map[v] if q not in mapped_set)
    
