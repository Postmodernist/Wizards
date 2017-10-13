from model.ActionType import ActionType
import math
from helper_classes import *
from utilities import *
from config import *

############################# Main classes #############################

class Critic:

    def __init__(self, strategy):
        self.strategy   = strategy
        self.actor      = strategy.actor
        self._me        = None
        self._world     = None
        self._game      = None
        self.lane       = ''
        self.waypoints  = []
        self.reset()

    def reset(self):
        self.dead           = True
        self.waypoint_idx   = 0
        self.enemies_near   = []
        self.allies_near    = []

    def update(self):

        def get_nearby_allies():
            t = []
            t.extend(o for o in self._world.minions if o.faction == self._me.faction)
            t.extend(o for o in self._world.wizards if o.faction == self._me.faction \
                and o.id != self._me.id)
            t_near = [o for o in t if distance(self.center, (o.x, o.y)) < ALLIES_DISTANCE]
            return t_near

        def get_nearby_enemies():
            t = []
            t.extend(o for o in self._world.minions if o.faction not in (self._me.faction, 2, 3))
            t.extend(o for o in self._world.buildings if o.faction not in (self._me.faction, 2, 3))
            t.extend(o for o in self._world.wizards if o.faction != self._me.faction)
            t_near = [o for o in t if distance(self.center, (o.x, o.y)) < ENEMIES_DISTANCE]
            return t_near

        def get_nearby_trees():
            t = [o for o in self._world.trees \
                 if distance(self.center, (o.x, o.y)) < self._game.staff_range+o.radius]
            return t

        def get_enemy_base():
            for o in self._world.buildings:
                if o.type == 1 and o.faction != self._me.faction:
                    return o

        def closest(t):
            d = distance(self.center, (t[0].x, t[0].y))
            res = t[0]
            if len(t) > 1:
                for o in t[1:]:
                    d_new = distance(self.center, (o.x, o.y))
                    if d_new < d: d = d_new; res = o
            return res

        def injured_list(t):
            return [o for o in t if o.life < o.max_life*ENEMY_INJURED_HP_COEF]

        def weak_list(t):
            return [o for o in t if o.life < o.max_life*ENEMY_WEAK_HP_COEF]

        def too_close_list(t):
            return [o for o in t if distance(self.center, (o.x, o.y)) < FIGHTER_TOO_CLOSE_DISTANCE]

        def engage_dist_list(t):
            return [o for o in t if distance(self.center, (o.x, o.y)) < self.engage_dist]

        def wizards_list(t):
            return [o for o in t if o in self._world.wizards]

        def buildings_list(t):
            return [o for o in t if o in self._world.buildings]

        def is_near_enemy_base():
            if distance(self.center, (3600, 400)) < 800: return True
            else: return False



        self.update_waypoints()

        ## reset if dead
        if self._me.life == 0:
            self.actor.reset()
            self.reset()
            return
        else:
            self.dead = False

        self.center         = (self._me.x, self._me.y)
        self.enemies_near   = get_nearby_enemies()
        self.allies_near    = get_nearby_allies()
        self.trees_near     = get_nearby_trees()
        self.engage_dist    = self._me.cast_range*FIGHTER_ENGAGE_DISTANCE_COEF
        self.enemy_base     = get_enemy_base()
        near_enemy_base     = is_near_enemy_base()
        
        ## update waypoint
        for wp in self.waypoints[:-1]:
            if distance(self.center, wp) < STRATEGY_WAYPOINT_TOLERANCE:
                if self.waypoint_idx < len(self.waypoints)-2:
                    self.waypoint_idx = self.waypoints.index(wp)+1
                else:
                    self.waypoint_idx = self.waypoints.index(wp)

        ## if we have bad guys around - pick one to fight!
        if self.enemies_near:

            weak_wizards        = wizards_list(weak_list(self.enemies_near))
            weak_buildings      = buildings_list(weak_list(self.enemies_near))
            close_enemies       = too_close_list(self.enemies_near)
            close_wizards       = wizards_list(close_enemies)
            engaging_wizards    = wizards_list(engage_dist_list(self.enemies_near))
            injured_enemies     = injured_list(self.enemies_near)
            injured_wizards     = wizards_list(injured_enemies)

            ## priorities
            if   weak_wizards:      target = closest(weak_wizards)
            elif close_wizards:     target = closest(close_wizards)
            elif close_enemies:     target = closest(close_enemies)
            elif self.trees_near:   target = closest(self.trees_near)
            # elif engaging_wizards:  target = closest(engaging_wizards)
            elif weak_buildings:    target = closest(weak_buildings)
            elif injured_wizards:   target = closest(injured_wizards)
            elif injured_enemies:   target = closest(injured_enemies)
            else:                   target = closest(self.enemies_near)

        elif self.trees_near:       target = closest(self.trees_near)
        else:                       target = None
            
        self.actor.target       = target

        if not target:
            self.actor.state        = 'traveller'
            self.actor.destination  = self.waypoints[self.waypoint_idx]
        
        elif self.enemy_base and self.enemy_base.life < self.enemy_base.max_life*ENEMY_WEAK_HP_COEF:
            self.actor.state        = 'fighter'
                    
        elif near_enemy_base:
            self.actor.state        = 'traveller'
            self.actor.destination  = self.waypoints[self.waypoint_idx]

        elif self.enemies_near:
            self.actor.state        = 'fighter'

        else:
            self.actor.state        = 'traveller'
            self.actor.destination  = self.waypoints[self.waypoint_idx]

    def update_waypoints(self):
        if   self._me.id in (1, 2, 6, 7):   self.lane = 'top'
        elif self._me.id in (3, 8):         self.lane = 'mid'
        elif self._me.id in (4, 5, 9, 10):  self.lane = 'bot'
        self.waypoints = WAYPOINTS[self.lane]


##############################################################################


class Actor:

    def __init__(self, strategy):
        self.strategy       = strategy
        self.cruise_control = CruiseControl(strategy)
        self._me            = None
        self._world         = None
        self._game          = None
        self.state          = 'traveller'
        self.reset()

    def reset(self):
        self.target         = None
        self.destination    = None
        self._last_hp = 100
        self._fleeing = 0

    def update(self):

        self.critic         = self.strategy.critic
        self.center         = (self._me.x, self._me.y)
        self.melee_d        = self._game.staff_range
        self.range_d        = self._me.cast_range
        self.tgt_pos        = None
        turn                = 0.0
        cast_angle          = 0.0
        min_cast_distance   = 0.0
        action              = ActionType.NONE

        ## always attack, no matter the state
        if self.target:
    
            self.tgt_pos    = (self.target.x, self.target.y)
            self.tgt_a      = math.atan2((self.tgt_pos[1]-self.center[1]), \
                              (self.tgt_pos[0]-self.center[0]))
            self.tgt_a_rel  = rel_angle(self._me.angle, self.tgt_a)
            self.tgt_d      = distance(self.center, self.tgt_pos)

            ## turn to target
            turn            = self.tgt_a_rel

            ## attack if we can
            if abs(self.tgt_a_rel) <= self._game.staff_sector/2:
                range_cooldown = self._me.remaining_cooldown_ticks_by_action[2]
                ## range
                if self.tgt_d <= (self.range_d+self.target.radius-self._game.magic_missile_radius) \
                and not range_cooldown:
                    cast_angle          = self.tgt_a_rel
                    min_cast_distance   = self.tgt_d - self.target.radius + \
                                          self._game.magic_missile_radius
                    action              = ActionType.MAGIC_MISSILE
                ## melee
                elif self.tgt_d <= self.melee_d+self.target.radius:
                    cast_angle          = self.tgt_a_rel
                    min_cast_distance   = self.tgt_d - self.target.radius
                    action              = ActionType.STAFF

        else:
            ## turn to movement direction
            turn = rel_angle(self._me.angle, self.cruise_control.move_angle)

        if self.state == 'traveller':
            pass

        elif self.state == 'fighter':
            if not self._fleeing: self.fighter_micro()

        if self._fleeing: self._fleeing -= 1
        
        self._last_hp                   = self._me.life
        ## action
        self.strategy.turn              = turn
        self.strategy.cast_angle        = cast_angle
        self.strategy.min_cast_distance = min_cast_distance
        self.strategy.action            = action
        ## movement
        self.cruise_control.destination = self.destination 
        self.cruise_control.update()

    def fighter_micro(self):

        def get_steer_point():
            if self.critic.lane == 'top': steer_a = rel_angle(0, self.tgt_a+math.pi/3)
            else:                         steer_a = rel_angle(0, self.tgt_a-math.pi/3)
            x = self.center[0] + math.cos(steer_a)*self.tgt_d/2
            y = self.center[1] + math.sin(steer_a)*self.tgt_d/2
            ## check map boundary
            if x < self._me.radius:             x = self._me.radius
            if x > GRID_WIDTH-self._me.radius:  x = GRID_WIDTH-self._me.radius
            if y < self._me.radius:             y = self._me.radius
            if y > GRID_HEIGHT-self._me.radius: y = GRID_HEIGHT-self._me.radius
            return (x, y)

        def is_bad_wiz_near():
            for creep in self.critic.enemies_near:
                if creep in self._world.wizards and creep.faction != self._me.faction:
                    return True
            return False

        flee_wp_idx         = self.critic.waypoint_idx-2
        if flee_wp_idx < 0: flee_wp_idx = 0
        engage_dist         = self.range_d*FIGHTER_ENGAGE_DISTANCE_COEF
        steer_point         = get_steer_point()
        flee_point          = self.critic.waypoints[flee_wp_idx]
        enemy_wiz_near      = is_bad_wiz_near()

        ## flee - in trouble
        if (self._me.life < self._last_hp) \
        or ((self._me.life < FIGHTER_HP_FLEE) and (self.tgt_d < ENEMIES_DISTANCE)):
            self.destination = flee_point
            self._fleeing = FIGHTER_FLEE_TICKS
        
        ## engage - allies around, in good shape
        elif not enemy_wiz_near \
        and  self.critic.allies_near and (self._me.life > FIGHTER_HP_CAUCIOUS):
            if self.tgt_d > engage_dist:    self.destination = steer_point
            else:                           self.destination = self.tgt_pos

        ## engage - weak wiz, good shape
        elif self.target in self._world.wizards \
        and  (self.target.life < self.target.max_life*ENEMY_WEAK_HP_COEF) \
        and  (self._me.life > FIGHTER_HP_CAUCIOUS):
            self.destination = self.tgt_pos

        ## engage - winning a wiz fight, but do not move too close
        elif self.target in self._world.wizards \
        and  (self._me.life > self.target.life) \
        and  (self.tgt_d > engage_dist):
            self.destination = steer_point

        ## flee - too close
        elif self.tgt_d < self.range_d-5:
            self.destination = flee_point

        ## engage - too far
        elif self.tgt_d > self.range_d:
            self.destination = self.tgt_pos

        ## hold position
        else:
            self.destination = self.center
