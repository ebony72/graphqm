#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon May  1 11:22:16 2023

@author: sanjiangli
"""

import networkx as nx
# import time

class Map:   
    #sl result is a dict, i.e., a mapping from logical qubits to physical qubits
    def __init__(self, result):  
        self.__subMap = []
        self.__gMap = []    
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
    def __init__(self, g, G, result, stop=None):
        self.subgraph = g
        self.graph = G
        self.stop = stop
        self.result = result
        self.is_over = False
        self.last_vertex = None
        self.vertex_seq = []
        
        while not self.is_over:
            self.dfsMatch()
            
    #sl divide the graph neighborhood of a vertex into two disjoint parts: pre (in map) and succ (not in map)
    def preSucc(self, vertexNeighbor, graphtype):
           
        if graphtype == 'subgraph':
            PRE = [vertex  for vertex in vertexNeighbor if vertex in self.curMap.subMap()]
            SUC = [vertex  for vertex in vertexNeighbor if vertex not in self.curMap.subMap()]

        else: # 'graph'
            PRE = [vertex  for vertex in vertexNeighbor if vertex in self.curMap.gMap()]
            SUC = [vertex  for vertex in vertexNeighbor if vertex not in self.curMap.gMap()]

        return PRE, SUC


    def isMeetRules(self, v1, v2):
            
        if not self.result:
            return True     
        
        #if not nx.is_connected(subgraph):
        #    print('Attention: The subgraph is not connected!')
        
        v1Neighbor = list(nx.all_neighbors(self.subgraph, v1))
        v2Neighbor = list(nx.all_neighbors(self.graph, v2))

        self.curMap = Map(self.result)               
        v1Pre, v1Succ = self.preSucc(v1Neighbor, 'subgraph')
        v2Pre, v2Succ = self.preSucc(v2Neighbor, 'graph')
        
        '''The case when deg(subgraph,v1) > deg(graph, v2) has been excluded!'''

        ''' v1 cannot have more predecessors/successors than v2'''
        if len(v1Pre) > len(v2Pre) or len(v1Succ) > len(v2Succ):
            return False
                       
        for pre in v1Pre:
            if self.result[pre] not in v2Pre:
                return False
        
        ''' v1 cannot have more successors that are map neighbours than v2'''
        len1 = len(set(v1Neighbor) & set(self.subMNeighbor)) #subMNeighborhood
        len2 = len(set(v2Neighbor) & set(self.gMNeighbor))

        if len1 > len2:
            return False
        return True
        

    def dfsMatch(self): #sl stop is the time limit
        
        # print(len(self.result), self.last_vertex)
        if len(self.result) == len(nx.nodes(self.subgraph)): # success
            print('Vf2 should have been completed!')
            self.is_over = True
            return self.result
        
        '''Construct the current neighborhoods of the mapping'''  
        self.curMap = Map(self.result)
        self.subMNeighbor = self.curMap.neighbor(self.subgraph, 0) #unmapped nghbrs 
        self.gMNeighbor = self.curMap.neighbor(self.graph, 1) 

        if self.subMNeighbor and len(self.subMNeighbor) > len(self.gMNeighbor):  # fail
            return self.result

        if not self.subMNeighbor:
            '''If all nghbrs are mapped: either the whole cc are mapped or the result is empty'''
            '''The subgraph is disconnected or the result is empty!'''
            '''If the subgraph is connected, then subMNeighbour is empty 
                iff curMap is full, which should have terminated the program!'''     
                
            # print('Check if subgraph is connected', nx.is_connected(self.subgraph))    
            X = list(set(nx.nodes(self.subgraph)) - set(self.curMap.subMap()))
            gNMNeighbor = list(set(nx.nodes(self.graph)) - set(self.curMap.gMap()))
        else:
            X = self.subMNeighbor
            gNMNeighbor = self.gMNeighbor[:]
            
        '''sub- and gNMNeighbor are only used for selecting the candidate pairs'''
        
        '''Rank the unmapped neighbors in the subgraph by their degrees'''    
        subNMN_deg = list([nx.degree(self.subgraph, v), v] for v in X)
        subNMN_deg.sort(key=lambda t: t[0], reverse=True)

        '''Select the unmapped node with the largest degree!'''
        v1 =  subNMN_deg[0][1]
        
        if len(self.result) == 0:
            print('the first vertex is', v1)
            self.first_vertex = v1
        
        '''Our AGs are always connected. gMNeighbor is empty iff result is empty!'''  
        '''If subgraph is disconnected, we should expand the selection!'''

        # if not self.subMNeighbor:  
        #     gNMNeighbor = list(set(nx.nodes(self.graph)) - set(self.curMap.gMap()))
        # else: 
        #     gNMNeighbor = self.gMNeighbor[:]

        '''Remove those graph neighbours which cannot match the suggraph candidate node''' 
        gNMNeighbor = [ t for t in gNMNeighbor if\
                       nx.degree(self.subgraph, v1) <= nx.degree(self.graph,t)]
        if not gNMNeighbor:
            return self.result

        self.last_vertex = v1
        self.vertex_seq.append(v1)
        
        for v2 in gNMNeighbor:
            if self.isMeetRules(v1, v2):
                self.result[v1] = v2
                self.dfsMatch()
                print('__'*len(self.result), v1, v2, self.result)

                if len(self.result) == len(nx.nodes(self.subgraph)):
                    self.is_over = True
                    return self.result
                else:
                    self.result.pop(v1)
        
        if v1 == self.first_vertex:
            self.is_over = True
            print('The search failed and subgraph is not embeddable in graph!')
        
        """ After examining all possible extension, we found that none is good. """
        return self.result
                
        # self.vertex_seq.remove(v1)
        # if not self.vertex_seq: 
        #     self.is_over = True