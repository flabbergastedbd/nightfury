from rlpy.Domains.Domain import Domain
from urlparse import urlparse

import numpy as np
import os
import json
import random
import importlib
import hack_actions


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
        self.datastore = Datastore()
        self.continuous_dims = []
        self.DimNames = self.datastore.ordered_dim_names
        self.actions = [cls() for cls in hack_actions.HackAction.__subclasses__()]
        self.actions_num = len(self.actions)
        self.statespace_limits = np.array([[0,5] for i in range(len(self.datastore.ordered_dim_names))])
        self.discount_factor = 0.9
        super(HackDomain, self).__init__()
        self.s0()

    def s0(self):
        state = self.datastore.get_state(new=True)
        self.url = self.datastore.current_target
        return(state, self.isTerminal(), self.possibleActions())

    def possibleActions(self):
        pa = []
        zero_state_features = []
        state = self.datastore.get_state()
        for j, v in enumerate(state):
            if v == 0:
                zero_state_features.append(self.DimNames[j])
        for j, a in enumerate(self.actions):
            if len(list(set(a.dependent_dims) & set(zero_state_features))) == 0:
                pa.append(j)
        return(pa)

    def isTerminal(self):
        s = self.datastore.get('cms_version')
        return(s != 0)

    def step(self, a):
        result = self.actions[a].run(self.url)
        for k, v in result.items():
            self.datastore.set(k, v)
        t = self.isTerminal()
        r = self.GOAL_REWARD if t else self.STEP_REWARD
        self.datastore.save()
        return(r, self.datastore.get_state(), t, self.possibleActions())

    def showLearning(self, representation):
        terminal = self.isTerminal()
        actions = self.possibleActions()
        state = self.datastore.get_state()
        ba = representation.bestActions(state, terminal, actions)
        if not terminal:
            # print("Possible Actions: %s " % (str(actions)))
            print("State: %s Best Action: %s" % (str(state), type(self.actions[ba[0]]).__name__))
        return


target_dict = {
    "cms": 0,
    "cms_version": 0,
    "port": 0,
    "protocol": 0
    "ssl_version": 0
}

class Datastore(object):
    def __init__(self, f='data.json'):
        self.f = f
        self.current_target = None
        if os.path.exists(self.f):
            with open(self.f, 'r') as fp:
                self.data = json.load(fp)
        else:
            self.data = {"targets":{}}
        self.ordered_dim_names = target_dict.keys()
        self.ordered_dim_names.sort()
        self.target_urls = ['https://www.drupal.org', 'http://typographica.org', 'http://www.mb-photography.com']

    def save(self):
        with open(self.f, 'w') as fp:
            json.dump(self.data, fp)

    def _get_prop_numbered_value(self, prop_name, prop_value):
        key = prop_name + "___set"
        try:
            dataset = self.data[key]
        except KeyError:
            self.data[key] = [0]
        finally:
            try:
                num_value = self.data[key].index(prop_value)
            except ValueError:
                self.data[key].append(prop_value)
                num_value = len(self.data[key]) - 1
            finally:
                return(num_value)

    def reset(self, target_url):
        url = urlparse(target_url)
        port = url.port
        if port == None:
            if url.scheme == 'http':
                port = 80
            elif url.scheme == 'https':
                port = 443
        temp_dict = dict(target_dict)
        temp_dict["port"] = self._get_prop_numbered_value('port', port)
        temp_dict["protocol"] = self._get_prop_numbered_value('protocol', url.scheme)
        self.data["targets"][target_url] = dict(temp_dict)

    def get(self, prop_name, target=None):
        target = target if target else self.current_target
        return(self.data["targets"][target][prop_name])

    def set(self, prop_name, prop_value, target=None):
        target = target if target else self.current_target
        try:
            targets = self.data["targets"][target]
        except KeyError:
            self.data["targets"][target] = dict(target_dict)
        finally:
            self.data["targets"][target][prop_name] = self._get_prop_numbered_value(prop_name, prop_value)

    def get_state(self, new=False):
        if new == True:
            self.current_target = random.choice(self.target_urls)
            self.reset(self.current_target)
        state = [self.data["targets"][self.current_target][x] for x in self.ordered_dim_names]
        return(state)
