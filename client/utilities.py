import math
from queue import PriorityQueue
from config import *

############################# Utilities #############################

def distance(p1, p2):
    return math.sqrt((p1[0]-p2[0])**2+(p1[1]-p2[1])**2)

def rel_angle(a1, a2):
    a_rel = a2 - a1
    if   a_rel < -math.pi: a_rel = -math.pi-a_rel
    elif a_rel >  math.pi: a_rel =  math.pi-a_rel
    return a_rel

def search_path(grid, nodes, start, goal):
    '''grid: weighted grid with walls. Returns shortest path.'''

    def neighbors(node):
        '''Returns a list of node neighbours.'''
        res = [(node[0]+x, node[1]+y) for x in range(-1, 2) for y in range(-1,2) \
               if  0 <= (node[0]+x) < nodes.shape[0] \
               and 0 <= (node[1]+y) < nodes.shape[1] \
               and (x != 0 or y != 0)]
        res = [node for node in res if node not in grid.walls]
        return res

    def cost(node_from, node_to):
        '''Assumes nodes are adjacent, including diagonal.'''
        move_cost = 0
        if node_from[0] == node_to[0] or node_from[1] == node_to[1]:
            move_cost = MOVE_COST
        else:
            move_cost = MOVE_COST_DIAG
        return move_cost+nodes[node_to]

    def manhattan_dist(p1, p2):
        '''Returns manhattan distance cost with diagonal moves.'''
        dx, dy = abs(p1[0]-p2[0]), abs(p1[1]-p2[1])
        if dx > dy: dx, dy = dy, dx
        return dx*MOVE_COST_DIAG+(dy-dx)*MOVE_COST

    def get_path(goal):
        '''Returns path.'''
        current = goal
        path = []
        while current != start:
            path.append(current)
            current = came_from[current]
        path.reverse()
        return path

    ## initialize
    frontier = PriorityQueue()
    came_from = {}
    cost_so_far = {}
    explored = {}
    frontier.put((0, start))
    came_from[start] = start
    cost_so_far[start] = 0
    ## search
    while True:
        while True: # pop queue until unexplored node
            if frontier.empty(): return [] # there is no path
            current = frontier.get()[1]
            if current not in explored: break
        if current == goal: # path found
            return get_path(goal)
        explored[current] = True # mark node as explored
        for next_node in neighbors(current):
            if next_node in explored: continue # skip all explored nodes
            new_cost = cost_so_far[current] + cost(current, next_node)
            if next_node not in cost_so_far or new_cost < cost_so_far[next_node]:
                cost_so_far[next_node] = new_cost
                priority = new_cost + manhattan_dist(next_node, goal)
                frontier.put((priority, next_node))
                came_from[next_node] = current
