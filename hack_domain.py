from rlpy.Domains.Domain import Domain
from hack_actions import *
import numpy as np
import random

class HackDomain(Domain):
    #: Reward for each timestep spent in the goal region
    GOAL_REWARD = 5
    #: Reward for each timestep
    STEP_REWARD = -1
    #: Set by the domain = min(100,rows*cols)
    episodeCap = 10

    def __init__(self):
        self.url = None
        self.start = 0
        self.statespace_limits = np.array([[0,3], [0, 1]])
        self.continuous_dims = []
        self.DimNames = ['cms', 'version']
        self.actions_num = 4
        self.discount_factor = 0.9
        self.actions = [WhatwebAction(), WpscanAction(), DroopescanAction(), JoomscanAction()]
        super(HackDomain, self).__init__()
        self.s0()

    def s0(self):
        self.url = random.choice(['https://www.drupal.org', 'http://typographica.org', 'http://www.mb-photography.com'])
        self.state = np.array([0 for dummy in xrange(0, self.state_space_dims)])
        return(self.state, self.isTerminal(), self.possibleActions())

    def possibleActions(self):
        pa = []
        for j, a in enumerate(self.actions):
            if 0 not in [self.state[i] for i in a.dependent_dims]:
                pa.append(j)
        return(pa)

    def isTerminal(self):
        s = self.state
        return(s[-1] != 0)

    def step(self, a):
        result = self.actions[a].run(self.url)
        for i in result:
            self.state[i[0]] = i[1]
        t = self.isTerminal()
        r = self.GOAL_REWARD if t else self.STEP_REWARD
        # print("Next State %s (Terminal: %r)" % (str(self.state), t))
        return(r, self.state.copy(), t, self.possibleActions())

    def showLearning(self, representation):
        terminal = self.isTerminal()
        actions = self.possibleActions()
        ba = representation.bestActions(self.state, terminal, actions)
        print("State: %s Best Action: %s" % (str(self.state), str(ba)))
        return
