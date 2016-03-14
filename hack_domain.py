from rlpy.Domains.Domain import Domain
from urlparse import urlparse
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

import numpy as np
import os
import re
import json
import random
import importlib
import hack_actions
import hack_parser

browser = webdriver.Firefox()


class HackDomain(Domain):
    #: Reward for each timestep spent in the goal region
    GOAL_REWARD = 10
    #: Reward for each timestep
    STEP_REWARD = -1
    #: Set by the domain = min(100,rows*cols)
    episodeCap = 5

    def __init__(self):
        self.start = 0
        self.datastore = Datastore()
        self.continuous_dims = []
        self.DimNames = self.datastore.ordered_dim_names
        self.actions = hack_actions.ACTIONS
        self.actions_num = len(self.actions)
        self.statespace_limits = np.array([[0,127] for i in range(len(self.datastore.ordered_dim_names))])
        self.discount_factor = 0.6
        super(HackDomain, self).__init__()
        self.s0()

        self._sink_environment = ''
        self._payloads_environment = []

    def s0(self):
        state = self.datastore.get_state(new=True)
        self._sink_environment = self.datastore.current_sink
        self._payloads_environment = []
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
        s = self.datastore.get('alert')
        return(s == 'True')

    def _update_state(self, alert=False):
        e = self._sink_environment
        parser = hack_parser.CustomHTMLParser(self.datastore.taint)
        parser.feed(e)
        c_chars = parser.get_control_chars()
        stack = parser.get_stack()
        self.datastore.set('data_context', parser.found_in_data)
        self.datastore.set('attribute_context', parser.found_in_tag_attr_param)
        self.datastore.set('value_context', parser.found_in_tag_attr_value)
        for i, div in zip(range(1, 3), stack[::-1]):
            self.datastore.set(str(i) + '_pd', div)
        for i, cc in zip(range(1, 3), list(c_chars)):
            self.datastore.set(str(i) + '_cc', cc)
        print("Sink : %s (%s)" % (e, self.datastore.get_verbose_state()))
        self.datastore.set('alert', alert)
        self.datastore.save()

    def _inject_into_environment(self, s):
        injection_index = self._sink_environment.index(self.datastore.taint)
        self._sink_environment = self._sink_environment[:injection_index] + s + self._sink_environment[injection_index:]

        self._payloads_environment.append(s)

        browser.get("data:text/html," + self._sink_environment.replace(self.datastore.taint, '<script>alert(9)</script>'))
        try:
            WebDriverWait(browser, 0.01).until(EC.alert_is_present(),
                'Timed out waiting for PA creation confirmation popup to appear.')
            alert = browser.switch_to_alert()
            alert.accept()
            alert = True
        except TimeoutException:
            alert = False
        self._update_state(alert=alert)

    def step(self, a):
        partial_payload = self.actions[a].run(self._payloads_environment)
        self._inject_into_environment(partial_payload)

        t = self.isTerminal()
        r = self.GOAL_REWARD if t else self.STEP_REWARD
        return(r, self.datastore.get_state(), t, self.possibleActions())

    def showLearning(self, representation):
        pass
        """
        terminal = self.isTerminal()
        actions = self.possibleActions()
        state = self.datastore.get_state()
        ba = representation.bestActions(state, terminal, actions)
        print(state)
        if not terminal:
            print("%s\nBest Action: %s\n\n" % (self.datastore.get_verbose_state(), str(actions[ba[0]])))
        """
        return


state_dict = {'alert': 0, 'attribute_context':0, 'value_context':0, 'data_context':0}
for i in range(1, 3):
    state_dict[str(i) + '_cc'] = 0
for i in range(1, 3):
    state_dict[str(i) + '_pd'] = 0
"""
for t in hack_actions.TAGS:  # Used to give relative numbering using xpath
    state_dict[t] = 0
for c in hack_actions.CONTROL_CHARS:  # Used to denote which characters are encoded
    state_dict[c] = 0
"""


class Datastore(object):
    def __init__(self, f='data.json'):
        self.f = f
        self.current_sink = None
        self._taint = 'abcdef'
        if os.path.exists(self.f):
            with open(self.f, 'r') as fp:
                self.data = json.load(fp)
        else:
            self.data = {"sinks":{}}
        self.ordered_dim_names = state_dict.keys()
        self.ordered_dim_names.sort()
        # self.all_sinks = ['<script alert();//></script>', '<script something="alert();//"></script>']
        self.all_sinks = [
            # '<div %s></div>' % (self.taint),
            '<div something="%s"></div>' % (self.taint),
            # '<img %s>' % (self.taint),
            '<img something="%s">' % (self.taint),
            # '<table %s></table>' % (self.taint),
            '<table something="%s"></table>' % (self.taint),
            # '<button %s></button>' % (self.taint),
            '<button something="%s"></button>' % (self.taint),
        ]
        # self.all_sinks = ['<script something="%s"></script>' % (self.taint)]

    @property
    def taint(self):
        return(self._taint)

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

    def _get_prop_string_value(self, prop_name, prop_number):
        key = prop_name + "___set"
        try:
            value = self.data[key][prop_number]
        except KeyError:
            value = ''
        return(value)

    def reset(self, sink):
        temp_dict = dict(state_dict)
        self.data["sinks"][sink] = dict(temp_dict)

    def get(self, prop_name, sink=None):
        sink = sink if sink else self.current_sink
        return(self._get_prop_string_value(prop_name, self.data["sinks"][sink][prop_name]))

    def set(self, prop_name, prop_value, sink=None):
        sink = sink if sink else self.current_sink
        try:
            targets = self.data["sinks"][sink]
        except KeyError:
            self.data["sinks"][sink] = dict(state_dict)
        finally:
            self.data["sinks"][sink][prop_name] = self._get_prop_numbered_value(prop_name, prop_value)

    def get_state(self, new=False):
        if new == True:
            self.current_sink = random.choice(self.all_sinks)
            self.reset(self.current_sink)
        state = [self.data["sinks"][self.current_sink][x] for x in self.ordered_dim_names]
        return(state)

    def get_verbose_state(self):
        s = ''
        for x in self.ordered_dim_names:
            if self.get(x):
                s += " %s: %s " % (x, str(self.get(x)))
        return(s)
