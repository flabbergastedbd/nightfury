from rlpy.Domains.Domain import Domain
from urlparse import urlparse
from selenium import webdriver

import numpy as np
import os
import re
import json
import random
import importlib
import hack_actions


class CustomHTMLParser(HTMLParser):
    def __init__(self):
        self.stack = []
        self.taint = 'alert()'
        self.found_in_tag_attr_param = False
        self.found_in_tag_attr_value = False
        self.found_in_data = False
        self.trace = ''

    @property
    def found(self):
        return (self.found_in_tag_attr_param or self.found_in_tag_attr_value or self.found_in_data)

    def handle_startag(self, tag, attrs):
        if self.found == False:
            if tag != 'div':
                self.stack.append(tag)
            for param, value in attrs:
                if self.taint in param:
                    self.found_in_tag_attr_param = True
                    self.trace = param
                elif self.taint in value:
                    self.found_in_tag_attr_value = True
                    self.trace = value

    def handle_endtag(self, tag):
        if self.found == False:
            if self.stack[-1] == tag:
                self.stack.pop()

    def handle_data(self, data):
        if self.found == False:
            if self.taint in data:
                self.trace = data
                self.found_in_data = True

    def handle_startendtag(self, tag, attrs):
        if self.found == False:
            self.handle_starttag(tag, attrs)
            self.handle_endtag(tag)

    def handle_comment(self, data):
        if self.found == False:
            if self.taint in data:
                self.found_in_data = True

    def get_control_chars(self):
        c_chars = ''
        if self.found_in_tag_attr_param:
            c_chars = c_chars + '>'
        elif self.found_in_tag_attr_value:
            c_chars = c_chars + '>'

            c_chars = self._sink_environment[(self._sink_environment.index(self.trace) - 1)] + c_chars

            # Tested  on "test(')', \"'\", {'taint':1}, \"(\", '\\'')"
            # Following four loops will remove all the arguments except the ones with the trace
            t = self.taint
            s = self.trace
            for m in re.findall(r"'(?:[^\\'\"]|(?:\\'))*'", s):
                if t not in m:
                    s = s.replace(m, '')
            for m in re.findall(r'"(?:[^\\"\']|(?:\\"))*"', s):
                if t not in m:
                    s = s.replace(m, '')
            if s.count('"') % 2 == 1:
                for m in re.findall(r"'(?:[^\\']|(?:\\'))*'", s):
                    if t not in m:
                        s = s.replace(m, '')
                for m in re.findall(r'"(?:[^\\"]|(?:\\"))*"', s):
                    if t not in m:
                        s = s.replace(m, '')
            elif s.count("'") % 2 == 1:
                for m in re.findall(r'"(?:[^\\"]|(?:\\"))*"', s):
                    if t not in m:
                        s = s.replace(m, '')
                for m in re.findall(r"'(?:[^\\']|(?:\\'))*'", s):
                    if t not in m:
                        s = s.replace(m, '')

            for c_plus, c_minus in hack_actions.COUNTER_CONTROL_CHARS.items():
                for m in re.findall(r"\\%c[^\\%c]*\\%c" % (c_plus, c_minus, c_minus), s):
                    if t not in m:
                        s = s.replace(m, '')
            temp_trace = s

            temp_trace = temp_trace[temp_trace.index(self.taint)+len(self.taint):]

            temp_control_chars = dict(hack_actions.COUNTER_CONTROL_CHARS)
            temp_control_chars.update(hack_actions.MASTER_COUNTER_CONTROL_CHARS)
            s = temp_trace
            temp_trace = ''
            for c in s:
                if c in temp_control_chars.values():
                    temp_trace += c
            c_chars = temp_trace + c_chars
            return(c_chars)


class HackDomain(Domain):
    #: Reward for each timestep spent in the goal region
    GOAL_REWARD = 100
    #: Reward for each timestep
    STEP_REWARD = -1
    #: Set by the domain = min(100,rows*cols)
    episodeCap = 10

    def __init__(self):
        self.start = 0
        self.datastore = Datastore()
        self.continuous_dims = []
        self.DimNames = self.datastore.ordered_dim_names
        self.actions = hack_actions.ACTIONS
        self.actions_num = len(self.actions)
        self.statespace_limits = np.array([[0,1000] for i in range(len(self.datastore.ordered_dim_names))])
        self.discount_factor = 0.9
        super(HackDomain, self).__init__()
        self.s0()

        self.browser = webdriver.Firefox()
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
        s = self.datastore.get('cms_version')
        return(s != 0)

    def _update_state(self):
        e = self._sink_environment
        parser = CustomHTMLParser()
        parser.feed(e)
        c_chars = parser.get_control_chars()
        stack = parser.stack

    def _inject_into_environment(self, s):
        injection_index = self._sink_environment.index('alert()')
        self._sink_environment = self._sink_environment[:injection_index] + s + self._sink_environment[injection_index:]

        self._payloads_environment.append(s)

        self.browser.get("data:text/html," + self._sink_environment)

    def step(self, a):
        result = self.actions[a].run()
        self._inject_into_environment(result)

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
            print("%s\nBest Action: %s\n\n" % (self.datastore.get_verbose_state(), type(self.actions[ba[0]]).__name__))
        return


state_dict = {'xpath': 0, 'control_chars': 0}
for t in hack_actions.TAGS:  # Used to give relative numbering using xpath
    state_dict[t] = 0
for c in hack_actions.CONTROL_CHARS:  # Used to denote which characters are encoded
    state_dict[c] = 0


class Datastore(object):
    def __init__(self, f='data.json'):
        self.f = f
        self.current_sink = Nones
        if os.path.exists(self.f):
            with open(self.f, 'r') as fp:
                self.data = json.load(fp)
        else:
            self.data = {"sinks":{}}
        self.ordered_dim_names = state_dict.keys()
        self.ordered_dim_names.sort()
        self.all_sinks = ['<div anything="alert()"></div>']

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
        return(self.data["sinks"][sink][prop_name])

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
            s += "%s: %s\t" % (x, str(self._get_prop_string_value(x, self.data["sinks"][self.current_sink][x])))
        return(s)