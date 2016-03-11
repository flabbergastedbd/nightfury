import os
import re
import md5
import json
import subprocess
import numpy as np

from urlparse import urlparse

ACTIONS = []

class HackAction(object):
    dependent_dims = []
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



class TagAction(HackAction):
    """
    Action representing a HTML tag
    """
    pass

# TAGS = ('a', 'abbr', 'acronym', 'address', 'applet', 'embed', 'object', 'area', 'article', 'aside', 'audio', 'b', 'base', 'basefont', 'bdi', 'bdo', 'big', 'blockquote', 'body', 'br', 'button', 'canvas', 'caption', 'center', 'cite', 'code', 'col', 'colgroup', 'colgroup', 'datalist', 'dd', 'del', 'details', 'dfn', 'dialog', 'dir', 'ul', 'div', 'dl', 'dt', 'em', 'embed', 'fieldset', 'figcaption', 'figure', 'figure', 'font', 'footer', 'form', 'frame', 'frameset', 'h1', 'h6', 'head', 'header', 'hr', 'html', 'i', 'iframe', 'img', 'input', 'ins', 'kbd', 'keygen', 'label', 'input', 'legend', 'fieldset', 'li', 'link', 'main', 'map', 'mark', 'menu', 'menuitem')
TAGS = ('a', 'embed', 'object', 'body', 'button', 'canvas', 'div', 'embed', 'figure', 'form', 'frame', 'iframe', 'img', 'input')
for i in TAGS:
    ACTIONS.append(TagAction(i))



class ControlAction(HackAction):
    """
    Action representing a control character
    """
    pass


CONTROL_CHARS = [' ', '"', "'", '(', ')', '*', '+', '-', ',', ';', '<', '>', '=', '[', ']', '{', '}', '`']
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
