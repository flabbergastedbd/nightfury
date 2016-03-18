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
    pass

ATTR_PARAMS = ('onerror', 'src')
for i in ATTR_PARAMS:
    ACTIONS.append(AttrParamAction(i))



class AttrValueAction(HackAction):
    """
    Action with attr value
    """
    dependent_dims = {"context": "attr_value"}
    pass

ATTR_VALUES = ['x', 'popup=1;']
for i in ATTR_VALUES:
    ACTIONS.append(AttrValueAction(i))


class DataAction(HackAction):
    """
    Action with data
    """
    dependent_dims = {"context": "data"}
    pass

DATA_VALUES = ['popup=1;']
for i in DATA_VALUES:
    ACTIONS.append(DataAction(i))


class TagAction(HackAction):
    """
    Action representing a HTML tag
    """
    dependent_dims = {'context': 'tag_name'}
    pass

# TAGS = ('a', 'abbr', 'acronym', 'address', 'applet', 'embed', 'object', 'area', 'article', 'aside', 'audio', 'b', 'base', 'basefont', 'bdi', 'bdo', 'big', 'blockquote', 'body', 'br', 'button', 'canvas', 'caption', 'center', 'cite', 'code', 'col', 'colgroup', 'colgroup', 'datalist', 'dd', 'del', 'details', 'dfn', 'dialog', 'dir', 'ul', 'div', 'dl', 'dt', 'em', 'embed', 'fieldset', 'figcaption', 'figure', 'figure', 'font', 'footer', 'form', 'frame', 'frameset', 'h1', 'h6', 'head', 'header', 'hr', 'html', 'i', 'iframe', 'img', 'input', 'ins', 'kbd', 'keygen', 'label', 'input', 'legend', 'fieldset', 'li', 'link', 'main', 'map', 'mark', 'menu', 'menuitem')
# TAGS = ('a', 'embed', 'object', 'body', 'button', 'canvas', 'div', 'embed', 'figure', 'form', 'frame', 'iframe', 'img', 'input', 'title', 'option', 'select')
TAGS = ['img']
for i in TAGS:
    ACTIONS.append(TagAction(i))



class ControlAction(HackAction):
    """
    Action representing a control character
    """
    pass


CONTROL_CHARS = [' ', '"', "'", '(', ')', '*', '+', '-', ',', ';', '<', '>', '=', '[', ']', '{', '}', '`', '/']
CONTROL_CHARS = [' ', '"', "'", '<', '>', '/', '=']
for i in CONTROL_CHARS:
    a = ControlAction(i)
    if i == '>':
        a.dependent_dims = {'context': 'start_tag_attr|end_tag_attr|attr_param|delim'}
    if i == '<':
        a.dependent_dims = {'context': 'data'}
    elif i == '/':
        a.dependent_dims = {'context': 'start_tag_name|delim'}
    elif i == '=':
        a.dependent_dims = {'context': 'delim'}
    elif i in ["'", '"', ' ']:
        a.dependent_dims = {'context': 'delim|attr_value'}

    ACTIONS.append(a)

MASTER_COUNTER_CONTROL_CHARS = {
    "'": "'",
    '"': '"',
}

COUNTER_CONTROL_CHARS = {
    '(': ')',
    '[': ']',
    '{': '}',
    '`': '`'
}
