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

ATTR_PARAMS = ('onerror', 'onload', 'src')
for i in ATTR_PARAMS:
    ACTIONS.append(AttrParamAction(i))



class AttrValueAction(HackAction):
    """
    Action with attr value
    """
    dependent_dims = {"context": "attr_value"}
    pass

ATTR_VALUES = ('x', 'data:text/html,<script>var popup = 1;</script>', 'var popup = 1;')
for i in ATTR_VALUES:
    ACTIONS.append(AttrValueAction(i))



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
for i in CONTROL_CHARS:
    ACTIONS.append(ControlAction(i))

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
