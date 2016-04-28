from rlpy.Domains.Domain import Domain
from urlparse import urlparse

import numpy as np
import os
import re
import json
import random
import hack_actions
import hack_parser



class HackDomain(Domain):
    #: Reward for each timestep spent in the goal region
    GOAL_REWARD = 10
    #: Reward for each timestep
    STEP_REWARD = -1
    #: Reward for failure
    FAIL_REWARD = -10
    #: Set by the domain = min(100,rows*cols)
    episodeCap = 20

    def __init__(self):
        self.start = 0
        self.datastore = Datastore()
        self.continuous_dims = []
        self.DimNames = self.datastore.ordered_dim_names
        self.actions = hack_actions.ACTIONS
        self.actions_num = len(self.actions)
        self.statespace_limits = np.array([[0,30] for i in range(len(self.datastore.ordered_dim_names))])
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
        s = self.datastore.get_state_dict()
        for j, a in enumerate(self.actions):
            if a.is_valid(s):
                pa.append(j)
        return(pa)

    def isTerminal(self):
        success, failure = self._is_terminal_list()
        return(success or failure)

    def _is_terminal_list(self):
        s = self.datastore.get('alert')
        c = (len(self.possibleActions()) == 0)
        return(s, c)

    def _update_state(self, alert=False):
        e = self._sink_environment
        parser = hack_parser.CustomHTMLParser(self.datastore.taint)
        parser.feed(e)
        c_chars = list(parser.get_control_chars())
        stack = parser.get_stack()[::-1]
        context, context_helper =  parser.get_context()
        self.datastore.set('context', context)
        self.datastore.set('context_helper', context_helper)

        if len(stack) < 2:
            stack += [[0, []]] * (2 - len(stack))
        for i, div_details in zip(range(1, 3), stack):
            div, attrs = div_details
            self.datastore.set(str(i) + '_tag', div)
            if len(attrs) < 2:
                attrs += [(0, 0)] * (2 - len(attrs))
            for j, attr_pair in zip(range(1, 3), attrs):
                self.datastore.set(str(i) + '_tag_' + str(j) + '_ap', attr_pair[0])
                self.datastore.set(str(i) + '_tag_' + str(j) + '_av', attr_pair[1])

        if len(c_chars) < 2:
            c_chars += [0] * (2 - len(c_chars))
        for i, cc in zip(range(1, 3), list(c_chars)):
            self.datastore.set(str(i) + '_cc', cc)

        if alert:
            with open('payloads.txt', 'a') as f:
                f.write('%s\n' % (e))
            print("Sink : %s (%s)" % (e, self.datastore.get_verbose_state()))
        self.datastore.set('alert', alert)
        self.datastore.save()

    def step(self, a):
        self._sink_environment, alert = self.actions[a].run(self._sink_environment, self.datastore.taint, self.datastore.get_state_dict())
        self._update_state(alert=alert)

        actions = self.possibleActions()
        terminal = self.isTerminal()
        success, failure = self._is_terminal_list()
        if success:
            r = self.GOAL_REWARD
        elif len(actions) == 0:
            r = self.FAIL_REWARD
            terminal = True
            actions = [len(self.actions) - 1]
            """
            print("Terminal due to lack of action")
            print(self._sink_environment)
            print(self.datastore.get_verbose_state())
            """
        else:
            r = self.actions[a].reward
        return(r, self.datastore.get_state(), terminal, actions)

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
    state_dict[str(i) + '_tag'] = 0
    for j in range(1, 3): # ap = attribute parameter
        state_dict[str(i) + '_tag_' + str(j) + '_ap'] = 0
        state_dict[str(i) + '_tag_' + str(j) + '_av'] = 0
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
        # NOTE: When you change this, please do corresponding changes in hack_actions.TAGS
        # Make sure you do it or else you are done for good
        self.all_sinks = ['<%s %s' % (tag, self.taint) for tag in hack_actions.TAGS
            # '<keygen %s' % (self.taint),
            # '<canvas %s' % (self.taint),
            # '<picture>%s' % (self.taint),
            # '<div class=%s' % (self.taint),
            # '<link %s' %(self.taint),
            # '%s' % (self.taint),
            # '<div src=x><img src=x onerror=%s' % (self.taint),
            # '<body %s' % (self.taint),
            # '<img %s' % (self.taint),
            # '<audio %s' % (self.taint),
            # '<video %s' % (self.taint),
            # '<object %s' % (self.taint),
            # '<img src=x onerror=%s' % (self.taint),
            # '<img %s' % (self.taint),
            # '<title>%s</title>' % (self.taint),
            # '<div %s></div>' % (self.taint),
            # '<div something="%s"></div>' % (self.taint),
            # "<div something='%s'></div>" % (self.taint),
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

    def _get_key(self, prop_name):
        key = prop_name + "___set"
        if re.search("[0-9]", prop_name) and re.search("_", prop_name):
            modified_prop_name = prop_name.split('_')[-1]
            key = modified_prop_name + "___set"
        return(key)

    def _get_prop_numbered_value(self, prop_name, prop_value):
        key = self._get_key(prop_name)
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
        key = self._get_key(prop_name)
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

    def get_state_dict(self):
        s_dict = {}
        for x in self.ordered_dim_names:
            s_dict[x] = self.get(x)
        return(s_dict)
