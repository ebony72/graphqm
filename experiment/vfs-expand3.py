#-*- coding:utf-8 -*-
# AUTHOR:   yaolili
# FILE:     vf.py
# ROLE:     vf2 algorithm
# CREATED:  2015-11-28 20:55:11
# MODIFIED: 2015-12-05 11:58:12
# ADDAPTED: 2019-06-25 for Quantum Circuit Transformation by Sanjiang Li (SL)
# all comments by SL started with '#sl'
import networkx as nx
import time

class Map:   
    #sl result is a dict, i.e., a mapping from logical qubits to physical qubits
    def __init__(self, result):  
        self.__subMap = []
        self.__gMap = []    
        if type(result) is not dict:
            print("Class Map __init__() argument type error! dict expected!")
            exit()
        if result:             
            for key in result:     
                self.__subMap.append(key)
                self.__gMap.append(result[key])
                
    def subMap(self): #sl: used when checking isMeetRules 
        return self.__subMap
        
    def gMap(self):
        return self.__gMap
            
    #type = 0, g=subGraph; type = 1, g=graph
    def neighbor(self, g, type):

        if not (type == 1 or type == 0):
            print("Class Map neighbor() argument value error! type expected 0 or 1!")
            exit()
                    
        if type:
            curMap = self.__gMap
        else:
            curMap = self.__subMap

        neighbor_set = set()
        for x in curMap:
            for q in nx.all_neighbors(g,x):
                neighbor_set.add(q)
        '''Return unmapped neighbors''' #sl
        neighbor = list(neighbor_set - set(curMap))
        if not neighbor and not neighbor_set <= set(curMap):
            raise Exception('Neighbor cannot be empty!')
                    
        return neighbor  

class Vf:

    __origin = None
    __sub = None

    #type = 0, pre; type = 1, succ
    #sl divide the graph neighborhood of a vertex into two disjoint parts: pre (in map) and succ (not in map)
    def preSucc(self, vertexNeighbor, map, type):
        #vertexNeighbor and map can be empty
           
        result = []
        #succ
        #sl successors are those neighbors that are not in map
        if type:
            for vertex in vertexNeighbor:
                if vertex not in map:                   
                    result.append(vertex)
        #pre
        #sl predecessors are those neighbors that are in map
        else:
            for vertex in vertexNeighbor:
                if vertex in map:
                    result.append(vertex)
        return result


    def isMeetRules(self, v1, v2, subgraph, graph, result, subMap, gMap, subMNeighbor, gMNeighbor):
            
        if not result:
            return True     
        #if not nx.is_connected(subgraph):
        #    print('Attention: The subgraph is not connected!')
        
        v1Neighbor = list(nx.all_neighbors(subgraph, v1))
        v2Neighbor = list(nx.all_neighbors(graph, v2))
                
        v1Pre = self.preSucc(v1Neighbor, subMap, 0)
        v1Succ = self.preSucc(v1Neighbor, subMap, 1)
        v2Pre = self.preSucc(v2Neighbor, gMap, 0)
        v2Succ = self.preSucc(v2Neighbor, gMap, 1)
        
        '''The case when deg(subgraph,v1) > deg(graph, v2) has been excluded!'''#sl

        ''' v1 cannot have more predecessors/successors than v2'''
        if len(v1Pre) > len(v2Pre) or len(v1Succ) > len(v2Succ):
            return False
                       
        for pre in v1Pre:
            if result[pre] not in v2Pre:
                return False
        
        ''' v1 cannot have more successors that are map neighbours than v2'''
        len1 = len(set(v1Neighbor) & set(subMNeighbor)) #subMNeighborhood
        len2 = len(set(v2Neighbor) & set(gMNeighbor))

        if len1 > len2:
            return False
        return True

    def nxt_pairs(self, subgraph, graph, result):
        '''Construct the current neighborhoods of the mapping'''
        curMap = Map(result) #sl create a Map object!            
        subMNeighbor = curMap.neighbor(subgraph, 0) #unmapped nghbrs := all nghbrs - mapped nghbrs
        gMNeighbor = curMap.neighbor(graph, 1)   
        
        # TODO: should subMNeighbor a subgraph of gMNeighbor? and 
        #  subMneighbor+curMap.subMap() a subgraph of gMneighbor+curMap.gMap()
        #  Make use of this fact and design an efficient algorithm 

        
        """ Select the next to-be-mapped node in subgraph and candidate nodes in graph. """ 

        if not subMNeighbor:

            """ If subgraph is connected then result should be empty """
            if nx.is_connected(subgraph) and len(result) > 0: 
                raise Exception ('The subgraph is disconnected!')

            X = list(set(nx.nodes(subgraph)) - set(curMap.subMap()))            
            gNMNeighbor = list(set(nx.nodes(graph)) - set(curMap.gMap()))
            
        else:
            
            X = subMNeighbor
            gNMNeighbor = gMNeighbor[:]

        '''Rank the unmapped neighbors by their degrees'''    
        subNMN_deg = list([nx.degree(subgraph, v), v] for v in X)
        subNMN_deg.sort(key=lambda t: t[0], reverse=True)
        
        '''Select the node with the largest degree!'''
        v1 =  subNMN_deg[0][1] #sl the next subgraph node to be mapped 
        print('__'*len(result), 'extend with node', v1)

        '''Remove those graph neighbours which cannot match the suggraph candidate node''' 
        gNMNeighbor = [ t for t in gNMNeighbor if\
                       nx.degree(subgraph, v1) <= nx.degree(graph,t)]
        
        return v1, X, curMap, subMNeighbor, gMNeighbor, gNMNeighbor
    
    

    def dfsMatch(self, subgraph, graph, result, stop): #sl stop is the time limit
        print('**'*len(result), '!dfsMatch called')
        print(result)
        # TODO: is stop enforced correctly?
        start_A = time.time()
        
        if len(result) == len(nx.nodes(subgraph)):
            return result
        
        v1, X, curMap, subMNeighbor, gMNeighbor, gNMNeighbor =  self.nxt_pairs(subgraph, graph, result)

        if subMNeighbor and len(subMNeighbor) > len(gMNeighbor): 
            return result
            
        if not gNMNeighbor:
            return result
        
        for v2 in gNMNeighbor:

            if(self.isMeetRules(v1, v2, subgraph, graph, result, curMap.subMap(),\
                                curMap.gMap(), subMNeighbor, gMNeighbor)):

                result[v1] = v2
                
                self.dfsMatch(subgraph, graph, result, stop)

                if len(result) == len(nx.nodes(subgraph)):
                    """ A complete embedding is found """
                    return result
                else:
                    """ The extension of result with {v1:v2} is failed."""
                    result.pop(v1)
        
        """ The extension of with {v1: } failed. We backtrack and 
            consider the next candidate value of the previous key in result """ 
            
        print('backtrack', result)