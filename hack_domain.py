from rlpy.Domains.Domain import Domain
from urlparse import urlparse
from selenium import webdriver
from selenium.common.exceptions import WebDriverException

import numpy as np
import os
import re
import json
import random
import nf_shared
import hack_actions
import hack_parser



class HackDomain(Domain):
    #: Reward for each timestep spent in the goal region
    GOAL_REWARD = 10
    #: Reward for each timestep
    STEP_REWARD = -1
    #: Set by the domain = min(100,rows*cols)
    episodeCap = 9

    def __init__(self):
        self.start = 0
        self.datastore = Datastore()
        self.continuous_dims = []
        self.DimNames = self.datastore.ordered_dim_names
        self.actions = hack_actions.ACTIONS
        self.actions_num = len(self.actions)
        self.statespace_limits = np.array([[0,20] for i in range(len(self.datastore.ordered_dim_names))])
        self.discount_factor = 0.6
        super(HackDomain, self).__init__()
        self.s0()

        self._sink_environment = ''
        self._payloads_environment = []

    def s0(self):
        state = self.datastore.get_state(new=True)
        self._sink_environment = self.datastore.current_sink
        self._payloads_environment = []
        self._update_state(alert=False)
        return(state, self.isTerminal(), self.possibleActions())

    def possibleActions(self):
        pa = []
        for j, a in enumerate(self.actions):
            good_to_go = True
            for dim_name, dim_value in a.dependent_dims.items():
                state_dim_value = self.datastore.get(dim_name)
                if state_dim_value == 0 or not re.search(dim_value, state_dim_value):
                    good_to_go = False
                    break
            if good_to_go:
                pa.append(j)
        return(pa)

    def isTerminal(self):
        s = self.datastore.get('alert')
        return(s)

    def _update_state(self, alert=False):
        e = self._sink_environment
        parser = hack_parser.CustomHTMLParser(self.datastore.taint)
        parser.feed(e)
        c_chars = list(parser.get_control_chars())
        stack = parser.get_stack()[::-1]
        attrs = parser.get_attrs()
        context, context_helper =  parser.get_context()
        if context: self.datastore.set('context', context)
        if context_helper: self.datastore.set('context_helper', context_helper)

        if len(attrs) < 5:
            attrs += [(0, 0)] * (5 - len(attrs))
        for i, attr_pair in zip(range(1, 6), attrs):
            self.datastore.set(str(i) + '_ap', attr_pair[0])
            self.datastore.set(str(i) + '_av', attr_pair[1])

        if len(stack) < 2:
            stack += [0] * (2 - len(stack))
        for i, div in zip(range(1, 3), stack):
            self.datastore.set(str(i) + '_pd', div)

        if len(c_chars) < 2:
            c_chars += [0] * (2 - len(c_chars))
        for i, cc in zip(range(1, 3), list(c_chars)):
            self.datastore.set(str(i) + '_cc', cc)

        print("Sink : %s (%s)" % (e, self.datastore.get_verbose_state()))
        self.datastore.set('alert', alert)
        self.datastore.save()

    def _inject_into_environment(self, s):
        injection_index = self._sink_environment.index(self.datastore.taint)
        self._sink_environment = self._sink_environment[:injection_index] + s + self._sink_environment[injection_index:]

        self._payloads_environment.append(s)

        # nf_shared.browser.get("data:text/html," + self._sink_environment.replace(self.datastore.taint, '<script>var popup = true;</script>'))
        nf_shared.browser.get("data:text/html,<script>var popup;</script>" + self._sink_environment.replace(self.datastore.taint, ''))
        try:
            r = nf_shared.browser.execute_script('return popup;');
            alert = True if r == 1 else False
        except WebDriverException:
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


state_dict = {'alert': 0, 'context':0, 'context_helper': 0}
for i in range(1, 3): # cc = control character
    state_dict[str(i) + '_cc'] = 0
for i in range(1, 3): # pd = parent div
    state_dict[str(i) + '_pd'] = 0
for i in range(1, 6): # ap = attribute parameter
    state_dict[str(i) + '_ap'] = 0
for i in range(1, 6): # av = attribute value
    state_dict[str(i) + '_av'] = 0
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
            # '<div>%s</div>' % (self.taint),
            # '<img src=x onerror="%s">' % (self.taint),
            # '<img src=x onerror=%s' % (self.taint),
            '<img %s' % (self.taint),
            # '<title>%s</title>' % (self.taint),
            #'<div %s></div>' % (self.taint),
            # '<div something="%s"></div>' % (self.taint),
            # "<div something='%s'></div>" % (self.taint),
            # '<img %s>' % (self.taint),
            # '<img something="%s">' % (self.taint),
            # "<img something='%s'>" % (self.taint),
            # '<table %s></table>' % (self.taint),
            # '<table something="%s"></table>' % (self.taint),
            # "<table something='%s'></table>" % (self.taint),
            # '<button %s></button>' % (self.taint),
            # '<button something="%s"></button>' % (self.taint),
            # "<button something='%s'></button>" % (self.taint),
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
