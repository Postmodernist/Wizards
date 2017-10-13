from model.ActionType import ActionType
from model.Game import Game
from model.Move import Move
from model.Wizard import Wizard
from model.World import World
from main_classes import *

class MyStrategy:
    
    def __init__(self):
        self.actor = Actor(self)
        self.critic = Critic(self)
        ## actions
        self.speed = 0.0
        self.strafe_speed = 0.0
        self.turn = 0.0
        self.cast_angle = 0.0
        self.min_cast_distance = 0.0
        self.action = ActionType.NONE
        ## dev
        self.dump_vars_flag = False

    def move(self, me: Wizard, world: World, game: Game, move: Move):
        self.init_tick(me, world, game, move)
        self.update()
        move.speed = self.speed
        move.strafe_speed = self.strafe_speed
        move.turn = self.turn
        move.cast_angle = self.cast_angle
        move.min_cast_distance = self.min_cast_distance
        move.action = self.action

    def init_tick(self, me, world, game, move):
        for o in [self, self.critic, self.actor]:
            o._me = me
            o._world = world
            o._game = game
        self._move = move

    def update(self):
        self.critic.update()
        if not self.critic.dead: self.actor.update()

        if self.dump_vars_flag:
            self.dump_vars_flag = False
            self.dump_vars(self._me)
            self.dump_vars(self._world)
            self.dump_vars(self._game)
            self.dump_vars(self._move)

    def dump_vars(self, namespace):
        var_list = [(v, namespace.__dict__[v]) for v in sorted(list(namespace.__dict__))]
        for n in self.__dict__:
            if self.__dict__[n] == namespace: name = n
        f = open(name+'_vars.txt', 'w')
        for v in var_list:
            f.write(v[0]+' = '+str(v[1])+'\n')
        f.close()
