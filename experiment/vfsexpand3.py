#-*- coding:utf-8 -*-
"""This module is used to simulate the recursion mechanism of vfs up to level 3 """

import networkx as nx

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
        print('__'*len(result), 'extend with node', v1, result)

        '''Remove those graph neighbours which cannot match the suggraph candidate node''' 
        gNMNeighbor = [ t for t in gNMNeighbor if\
                       nx.degree(subgraph, v1) <= nx.degree(graph,t)]
        
        return v1, X, curMap, subMNeighbor, gMNeighbor, gNMNeighbor
    
    

    def dfsMatch(self, subgraph, graph, result, stop): #sl stop is the time limit
        print('~~~~~~~~~~~~~~~~~~~~~~')
        print('!dfsMatch called')
        
        v1, X1, curMap, subMNeighbor, gMNeighbor, gNMNeighbor =  self.nxt_pairs(subgraph, graph, result)

        if not gNMNeighbor or (subMNeighbor and len(subMNeighbor) > len(gMNeighbor)): 
            print('The subgraph is not embeddable - type 1!', result)
            return result
            
        
        for u1 in gNMNeighbor:

            if(self.isMeetRules(v1, u1, subgraph, graph, result, curMap.subMap(),\
                                curMap.gMap(), subMNeighbor, gMNeighbor)):

                result[v1] = u1
                                
                v2, X2, curMap2, subMNeighbor2, gMNeighbor2, gNMNeighbor2 =\
                    self.nxt_pairs(subgraph, graph, result)
                    
                if not gNMNeighbor2 or (subMNeighbor2 and len(subMNeighbor2) > len(gMNeighbor2)): 
                    continue
                
                # print('__'*len(result), 'extend with node', v2, result)

                for u2 in gNMNeighbor2:
        
                    if(self.isMeetRules(v2, u2, subgraph, graph, result, curMap2.subMap(),\
                                        curMap2.gMap(), subMNeighbor2, gMNeighbor2)):
        
                        result[v2] = u2        
                        
                        v3, X3, curMap3, subMNeighbor3, gMNeighbor3, gNMNeighbor3 =\
                            self.nxt_pairs(subgraph, graph, result)
                            
                        if not gNMNeighbor3 or (subMNeighbor3 and len(subMNeighbor3) > len(gMNeighbor3)): 
                            continue
                                                
                        for u3 in gNMNeighbor3:
                
                            if(self.isMeetRules(v3, u3, subgraph, graph, result, curMap3.subMap(),\
                                                curMap3.gMap(), subMNeighbor3, gMNeighbor3)):
                
                                result[v3] = u3
                                if is_complete(result, subgraph):
                                    print('The subgraph is embeddable', result)
                                    return result
                                else:
                                    result.pop(v3)
                                    
                        print('backtrack', result)     
                        result.pop(v2)
                        
                print('backtrack', result)                        
                result.pop(v1)
            
        print('The subgraph is not embeddable!', result)
        return result
        
def is_complete(result, subgraph):
    if len(result) == len(nx.nodes(subgraph)):
        return True
    return False
        