import math
import numpy as np
from functools import reduce
from utilities import *
from config import *

############################# Helper classes #############################

class CruiseControl:
    '''Delivers agent to the destination by shortest path, avoiding collisions.'''
    
    def __init__(self, strategy):
        self.strategy   = strategy
        self.grid       = Grid(strategy)
        self.center     = (0.0, 0.0)
        self.reset()

    def reset(self):
        self.destination    = None
        self.path           = []
        self.move_angle     = 0.0
        self.move_vector    = (0.0, 0.0)

    def update(self):

        self.center = (self.strategy._me.x, self.strategy._me.y)
        self.grid.update()

        if not self.destination \
        or distance(self.center, self.destination) < PATH_DESTINATION_TOLERANCE:
            self.reset()
        else:
            nw = GRID_NODE_WIDTH
            ## get path
            start = (int(self.center[0]//nw), int(self.center[1]//nw))
            goal = (int(self.destination[0]//nw), int(self.destination[1]//nw))
            # ## search only in fraction of the grid
            # grid_x0 = start[0]-8
            # grid_y0 = start[1]-8
            # grid_x1 = start[0]+9
            # grid_y1 = start[0]+9
            # if grid_x0 < 0: grid_x0 = 0
            # if grid_y0 < 0: grid_y0 = 0
            # if grid_x1 > GRID_WIDTH/GRID_NODE_WIDTH-1:  grid_x0 = GRID_WIDTH/GRID_NODE_WIDTH-1
            # if grid_y1 > GRID_HEIGHT/GRID_NODE_WIDTH-1: grid_y0 = GRID_HEIGHT/GRID_NODE_WIDTH-1
            # nodes = self.grid.nodes[grid_x0:grid_x1, grid_y0:grid_y1]
            if goal not in self.grid.walls:
                path = search_path(self.grid, self.grid.nodes, start, goal)
                ## convert path nodes to world coordinates
                self.path = [(node[0]*nw+nw//2, node[1]*nw+nw//2) for node in path]
            else:
                self.path = []
            ## the last waypoint is the destination
            self.path.append(self.destination)

        self.update_move_vector()
        self.strategy.speed, self.strategy.strafe_speed = self.get_speed()

    def update_move_vector(self):

        def force(pos, f, dist=1, decay='none'):
            '''pos is for angle; f, dist and decay are for magnitude.
            decay: none, linear, poly. Returns force vector.'''
            if decay == 'linear': f *= 1/(dist*FORCE_DECAY_LIN)
            elif decay == 'poly': f *= 1/dist**FORCE_DECAY_POW
            x, y = pos[0]-self.center[0], pos[1]-self.center[1]
            a = math.atan2(y, x)
            return f*math.cos(a), f*math.sin(a)

        forces = []
        ## get waypoint attraction
        if self.path: forces.append(force(self.path[0], FORCE_WAYPOINT))
        ## get collidables repulsion
        for o in self.grid.obstacles:
            d = distance(self.center, o.center)-o.radius # distance from the boundary
            if d < COLLIDABLE_MAX_DIST: # only count nearby collidables
                forces.append(force(o.center, FORCE_COLLIDABLE, d, 'poly'))
        ## get map boundaries repulsion
        boundaries = [ \
            Obstacle((self.center[0], 0), 0),           # top
            Obstacle((0, self.center[1]), 0),           # left
            Obstacle((GRID_WIDTH, self.center[1]), 0),  # right
            Obstacle((self.center[0], GRID_HEIGHT), 0)] # bottom
        for o in boundaries:
            d = distance(self.center, o.center)
            if d < COLLIDABLE_MAX_DIST: forces.append(force(o.center, FORCE_COLLIDABLE, d, 'poly'))
        ## resolve forces
        f = reduce(np.add, forces, (0, 0)) 
        if (f[0] == 0) and (f[1] == 0): # zero resulting force
            self.move_angle = self.strategy._me.angle
            self.move_vector = (0, 0)
        else:
            self.move_angle = math.atan2(f[1], f[0]) # get force direction
            self.move_vector = (math.cos(self.move_angle), math.sin(self.move_angle))

    def get_speed(self):
        world_vec = np.array(self.move_vector).reshape((2,1)) # move vector (world)
        a = self.strategy._me.angle
        ## get rotation matrix
        wiz_rot = np.array(( math.cos(a), math.sin(a), \
                            -math.sin(a), math.cos(a))).reshape((2,2))
        wiz_vec = np.dot(wiz_rot, world_vec).reshape((2)) # move vector (wizard)
        return wiz_vec*100.0


class Grid:
    
    def __init__(self, strategy):
        self.strategy   = strategy
        self.shape      = (GRID_WIDTH, GRID_HEIGHT)
        size_x          = int(self.shape[0]//GRID_NODE_WIDTH)
        size_y          = int(self.shape[1]//GRID_NODE_WIDTH)
        self.nodes      = np.zeros((size_x, size_y), dtype = np.int)
        self.walls      = []
        self.obstacles  = []

    def update(self):
        self.nodes.fill(0)
        self.update_obstacles()
        self.walls = []
        dim = self.nodes.shape
        
        # update costs
        for o in self.obstacles:
            node_x0 = int((o.center[0]-o.radius)//GRID_NODE_WIDTH) # left
            node_y0 = int((o.center[1]-o.radius)//GRID_NODE_WIDTH) # top
            node_x1 = int((o.center[0]+o.radius)//GRID_NODE_WIDTH) # right
            node_y1 = int((o.center[1]+o.radius)//GRID_NODE_WIDTH) # bottom
        
            ## process nodes covered by obstacle
            for x in range(node_x0, node_x1+1):
                for y in range(node_y0, node_y1+1):
                    node = (x, y)
                    if node in self.walls: continue # skip walls
                    if not (0 <= x < dim[0]) or not (0 <= y < dim[1]): # index outside of the grid
                        continue 
                    node_center = ((x+0.5)*GRID_NODE_WIDTH, (y+0.5)*GRID_NODE_WIDTH)
                    d = distance(node_center, o.center)
                    if d > o.radius+GRID_NODE_WIDTH//2: continue # node is outside
                    if d < o.radius: # node center is covered -> mark wall
                        self.nodes[node] = GRID_NODE_WIDTH*MOVE_COST_UNCERTAIN
                        self.walls.append(node)
                    else: # node is partially covered
                        cost = int(GRID_NODE_WIDTH//2+o.radius-d)*MOVE_COST_UNCERTAIN
                        self.nodes[node] += cost

    def update_obstacles(self):
        self.obstacles = []
        groups = [self.strategy._world.buildings,
                  self.strategy._world.trees,
                  self.strategy._world.minions,
                  self.strategy._world.wizards]
        if self.strategy.actor.target:
            for group in groups:
                self.obstacles.extend(Obstacle((o.x, o.y), o.radius) for o in group \
                    if o.id != self.strategy._me.id and o.id != self.strategy.actor.target.id)
        else:
            for group in groups:
                self.obstacles.extend(Obstacle((o.x, o.y), o.radius) for o in group \
                    if o.id != self.strategy._me.id)



class Obstacle:
    
    def __init__(self, position, radius):
        self.center = position
        self.radius = radius
