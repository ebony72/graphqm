#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon May  1 11:22:16 2023

@author: sanjiangli
"""

import networkx as nx
import copy
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
        
        tempres = {}
        # tempres = {3: 1, 5: 6, 1: 2, 2: 7, 0: 0}
        # tempres = {35: 5, 10: 1, 32: 0, 33: 11, 38: 6, 37: 8, 19: 3, 49: 15, 51: 9, 6: 14, 2: 35, 12: 41, 28: 29, 11: 21}
        while not self.is_over:
            if len(tempres) == len(nx.nodes(self.subgraph)):
                self.result = tempres
                self.is_over = True
                break
            if len(self.result) == len(nx.nodes(self.subgraph)):
                self.is_over = True
                break
            if self.is_over:
                break
            tempres = self.dfsMatch(tempres)
            # self.result = copy.copy(tempres)
            

    def dfsMatch(self, tempres): #sl stop is the time limit
    
        if self.result:
            self.is_over = True
            return self.result
            
        print('Call Vf on: ', tempres)

    
        """After the last extension, check if tempre is complete"""
        if len(tempres) == len(nx.nodes(self.subgraph)): # success
            print('Mapping is Completed: ', tempres)
            self.is_over = True
            self.result = copy.copy(tempres)
            # print('Completed I', self.is_over, tempres)
            return self.result
        
        if self.is_over:
            # print('Completed O', self.is_over, self.result)
            # print('')
            return self.result
        
        '''Construct the current neighborhoods of the mapping'''  
        curMap = Map(tempres)
        subMNeighbor = curMap.neighbor(self.subgraph, 0) #unmapped nghbrs 
        gMNeighbor = curMap.neighbor(self.graph, 1) 

        if subMNeighbor and len(subMNeighbor) > len(gMNeighbor):  # fail
            # print('Extension Failed I')
            return tempres

        if not subMNeighbor:
            '''If all nghbrs are mapped: either the whole cc are mapped or the result is empty'''
            '''The subgraph is disconnected or the result is empty!'''
            '''If the subgraph is connected, then subMNeighbour is empty 
                iff curMap is full, which should have terminated the program!'''     
                
            # print('Check if subgraph is connected', nx.is_connected(self.subgraph))    
            X = list(set(nx.nodes(self.subgraph)) - set(curMap.subMap()))
            gNMNeighbor = list(set(nx.nodes(self.graph)) - set(curMap.gMap()))
        else:
            X = subMNeighbor
            gNMNeighbor = gMNeighbor[:]
            
        '''sub- and gNMNeighbor are only used for selecting the candidate pairs'''
        
        '''Rank the unmapped neighbors in the subgraph by their degrees'''    
        subNMN_deg = list([nx.degree(self.subgraph, v), v] for v in X)
        subNMN_deg.sort(key=lambda t: t[0], reverse=True)

        '''Select the unmapped node with the largest degree!'''
        v1 =  subNMN_deg[0][1]
        
        if len(tempres) == 0:
            # print('')
            # print('^^^^Start of the Search^^^^')
            print('the first vertex is', v1)
            self.first_vertex = v1
        

        '''Remove those graph neighbours which cannot match the suggraph candidate node''' 
        gNMNeighbor = [ t for t in gNMNeighbor if\
                       nx.degree(self.subgraph, v1) <= nx.degree(self.graph,t)]
        if not gNMNeighbor:
            if len(tempres) == 0:
                self.is_over = True
                return {}
            # print('Extension Failed II')
            return tempres

        self.last_vertex = v1
        self.vertex_seq.append(v1)
        
        result1 = copy.copy(tempres)
        for v2 in gNMNeighbor:
            if isMeetRules(tempres, v1, v2, self.subgraph, self.graph):
                tempres[v1] = v2
                print('__'*len(tempres), 'extend', v1, 'by', tempres[v1])
                tempres = self.dfsMatch(tempres)

                    
                if len(tempres) == len(nx.nodes(self.subgraph)):
                    self.is_over = True
                    self.result = copy.copy(tempres)
                    return tempres
                else:
                    tempres.pop(v1)
                
                
                if self.is_over:
                    self.result = copy.copy(tempres)
                    return self.result                  
        
        # print('^^'*len(tempres), v1, 'end of one round')

        if result1 == tempres and len(result1) == 0:
            self.is_over = True
            
        if result1 != tempres:
            print('check ss')
            print(result1)
            print(tempres)
            
        return tempres

    
#sl divide the graph neighborhood of a vertex into two disjoint parts: pre (in map) and succ (not in map)
def preSucc(vertexNeighbor, curMap, graphtype):
       
    if graphtype == 'subgraph':
        PRE = [vertex  for vertex in vertexNeighbor if vertex in curMap.subMap()]
        SUC = [vertex  for vertex in vertexNeighbor if vertex not in curMap.subMap()]

    else: # 'graph'
        PRE = [vertex  for vertex in vertexNeighbor if vertex in curMap.gMap()]
        SUC = [vertex  for vertex in vertexNeighbor if vertex not in curMap.gMap()]

    return PRE, SUC

def isMeetRules(tempres, v1, v2, subgraph, graph):
        
    if not tempres:
        return True     
    
    #if not nx.is_connected(subgraph):
    #    print('Attention: The subgraph is not connected!')
    
    v1Neighbor = list(nx.all_neighbors(subgraph, v1))
    v2Neighbor = list(nx.all_neighbors(graph, v2))

    curMap = Map(tempres)               
    v1Pre, v1Succ = preSucc(v1Neighbor, curMap, 'subgraph')
    v2Pre, v2Succ = preSucc(v2Neighbor, curMap, 'graph')
    subMNeighbor = curMap.neighbor(subgraph, 0) #unmapped nghbrs 
    gMNeighbor = curMap.neighbor(graph, 1)  
    
    '''The case when deg(subgraph,v1) > deg(graph, v2) has been excluded!'''

    ''' v1 cannot have more predecessors/successors than v2'''
    if len(v1Pre) > len(v2Pre) or len(v1Succ) > len(v2Succ):
        return False
                   
    for pre in v1Pre:
        if tempres[pre] not in v2Pre:
            return False
    
    ''' v1 cannot have more successors that are map neighbours than v2'''
    len1 = len(set(v1Neighbor) & set(subMNeighbor)) #subMNeighborhood
    len2 = len(set(v2Neighbor) & set(gMNeighbor))

    if len1 > len2:
        return False
    return True