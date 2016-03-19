import os
import re
import md5
import json
import subprocess
import numpy as np

from urlparse import urlparse

ACTIONS = []

class HackAction(object):
    dependent_dims = {}
    dependency_dims = []
    def __init__(self, s):
        self.string = s or ''

    def hash_string(self, s):
        m = md5.new()
        m.update(s)
        return(m.hexdigest())

    def is_valid(self, s):
        good_to_go = True
        for dim_name, required_dim_value in self.dependent_dims.items():
            state_dim_value = s[dim_name]
            if state_dim_value == 0 or not re.search(required_dim_value, state_dim_value):
                good_to_go = False
                break
        return good_to_go

    def run(self, payload_list):
        return(self.string)

    def __str__(self):
        return(self.string)

    def __unicode__(self):
        return(self.string)



class AttrParamAction(HackAction):
    """
    Action representing a event handler
    """
    dependent_dims = {'context': 'attr_param'}

    def is_valid(self, s):
        good_to_go = True
        for feature_name, feature_value in s.items():
            if feature_name.endswith("_ap") and feature_value == self.string:
                good_to_go = False
                break
        return(good_to_go and super(AttrParamAction, self).is_valid(s))


ATTR_PARAMS = ('onblur', 'onerror', 'src', 'autofocus', 'onload', 'href')
for i in ATTR_PARAMS:
    ACTIONS.append(AttrParamAction(i))



class AttrValueAction(HackAction):
    """
    Action with attr value
    """
    dependent_dims = {"context": "attr_value_start_delim|attr_value$"}  # Either without delim or with delim
    def is_valid(self, s):
        good_to_go = True
        if s['context_helper'] in ATTR_PARAMS: # If one attr value is already present then no other ATTR value is needed
            for fname, fvalue in s.items():
                if fname != 'context_helper' and fvalue == s['context_helper']:
                    if not s[fname.replace('p', 'v')]:
                        good_to_go = True
                    else:
                        good_to_go = False
                    break
        return(good_to_go and super(AttrValueAction, self).is_valid(s))

ATTR_VALUES = ['x', 'popup=1;']
for i in ATTR_VALUES:
    ACTIONS.append(AttrValueAction(i))


class DataAction(HackAction):
    """
    Action with data
    """
    dependent_dims = {"context": "data"}
    pass

# DATA_VALUES = ['popup=1;']
DATA_VALUES = []
for i in DATA_VALUES:
    ACTIONS.append(DataAction(i))


class TagAction(HackAction):
    """
    Action representing a HTML tag
    """
    dependent_dims = {'context': 'tag_name'}
    pass

# TAGS = ('a', 'abbr', 'acronym', 'address', 'applet', 'embed', 'object', 'area', 'article', 'aside', 'audio', 'b', 'base', 'basefont', 'bdi', 'bdo', 'big', 'blockquote', 'body', 'br', 'button', 'canvas', 'caption', 'center', 'cite', 'code', 'col', 'colgroup', 'colgroup', 'datalist', 'dd', 'del', 'details', 'dfn', 'dialog', 'dir', 'ul', 'div', 'dl', 'dt', 'em', 'embed', 'fieldset', 'figcaption', 'figure', 'figure', 'font', 'footer', 'form', 'frame', 'frameset', 'h1', 'h6', 'head', 'header', 'hr', 'html', 'i', 'iframe', 'img', 'input', 'ins', 'kbd', 'keygen', 'label', 'input', 'legend', 'fieldset', 'li', 'link', 'main', 'map', 'mark', 'menu', 'menuitem')
TAGS = ('embed', 'object', 'body', 'canvas', 'div', 'embed', 'form', 'frame', 'iframe', 'img', 'input', 'option', 'select')
# TAGS = ['img', 'title', 'audio', 'video', 'body', 'object']
for i in TAGS:
    a = TagAction(i)
    if i in ['title']:
        a.dependent_dims = {'context': 'chachina_radu'}
    ACTIONS.append(a)


class MasterControlAction(HackAction):
    """
    Action representing a control character
    """
    def is_valid(self, s):
        if s['context'] == 'attr_value_start_delim' or (s['context'] == 'attr_value_end_delim' and s['1_cc'] == self.string):
            return True
        return False

MASTER_CONTROL_CHARS = ['"', "'"]
# MASTER_CONTROL_CHARS = []
for i in MASTER_CONTROL_CHARS:
    a = MasterControlAction(i)
    ACTIONS.append(a)

MASTER_COUNTER_CONTROL_CHARS = {
    "'": "'",
    '"': '"',
}


class ControlAction(HackAction):
    """
    Action representing a control character
    """
    pass

CONTROL_CHARS = [' ', '(', ')', '*', '+', '-', ',', ';', '<', '>', '=', '[', ']', '{', '}', '`', '/']
CONTROL_CHARS = [' ', '<', '>', '/', '=']
CONTROL_CHARS = [' ', '<', '>', '/', '=']
for i in CONTROL_CHARS:
    a = ControlAction(i)
    if i == '>':
        a.dependent_dims = {'context': 'start_tag_attr|end_tag_attr|attr_param|equal_dim|attr_delim'}
    if i == '<':
        a.dependent_dims = {'context': 'data'}
    elif i in [' ']:
        a.dependent_dims = {'context': 'attr_delim|attr_value_end_delim'}
    elif i in ['/']:
        a.dependent_dims = {'context': 'start_tag_attr|start_tag_name'}
    elif i == '=':
        a.dependent_dims = {'context': 'equal_delim'}
    ACTIONS.append(a)

COUNTER_CONTROL_CHARS = {
    '(': ')',
    '[': ']',
    '{': '}',
    '`': '`'
}
