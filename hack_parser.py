import re
import hack_actions

from HTMLParser import HTMLParser
from bs4 import BeautifulSoup

class CustomHTMLParser(HTMLParser):
    def __init__(self, taint):
        self.stack = []
        self.found = None
        self.found_helper = None
        self.attrs = []
        self.taint = taint
        self.trace = ''
        HTMLParser.__init__(self)

    def get_context(self):
        return(self.found or 0, self.found_helper or 0)

    def get_attrs(self):
        return(self.attrs)

    def feed(self, data):
        self._sink = data
        temp_data = re.sub('[^\'"]', '', data)
        temp_data = temp_data.replace('""', '')
        temp_data = temp_data.replace("''", '')
        if len(temp_data) > 0:
            data += temp_data[::-1]
        temp_data = re.sub('[^<>]', '', data)
        temp_data = temp_data.replace('<>', '')
        if temp_data == '<':
            data += '>'
        HTMLParser.feed(self, data)

    def get_stack(self):
        return(self.stack)

    def handle_starttag(self, tag, attrs):
        if not self.found:
            if tag != 'div':
                if tag.startswith(self.taint):
                    self.found = 'start_tag_name'
                    self.trace = tag
                elif self.taint in tag:
                    self.found = 'start_tag_attr'
                    self.trace = tag
                if tag.replace(self.taint, '') in hack_actions.TAGS:
                    self.stack.append(tag.replace(self.taint, ''))

            # New tag found, so override attributes
            self.attrs = []
            for param, value in attrs:
                if param.startswith(self.taint):
                    self.found = 'attr_param'
                    self.trace = param
                elif self.taint in param:
                    self.found ='equal_delim'
                    if param in hack_actions.ATTR_PARAMS: self.found_helper = param
                    self.trace = param

                if value and self.taint in value:
                    if value.startswith(self.taint):
                        if self._sink[self._sink.index(value) - 1] == '=':
                            # NOTE: Temporarily disabling to avoid string mess
                            # self.found = 'attr_value_delim'
                            self.found = 'attr_value_start_delim'
                        else:
                            self.found = 'attr_value'
                    elif self.taint in value:
                        if self._sink[self._sink.index(value) - 1] == '=':
                            self.found = 'attr_delim'
                        else:
                            self.found = 'attr_value_end_delim'
                        self.trace = value
                    if param in hack_actions.ATTR_PARAMS: self.found_helper = param
                    self.trace = value

                param = param.replace(self.taint, '')
                value = value.replace(self.taint, '') if value else value
                if param in hack_actions.ATTR_PARAMS and param not in [i[0] for i in self.attrs]:
                    if value and value in hack_actions.ATTR_VALUES:
                        self.attrs.append([param, value])
                    else:
                        self.attrs.append([param, None])

    def handle_endtag(self, tag):
        if not self.found:
            if tag.startswith(self.taint):
                self.found = 'end_tag_name'
            elif self.taint in tag:
                self.found = 'end_tag_attr'
            if len(self.stack) > 0 and self.stack[-1] == tag:
                self.stack.pop()

    def handle_data(self, data):
        if not self.found:
            if self.taint in data:
                self.trace = data
                self.found = 'data'

    def get_control_chars(self):
        c_chars = ''
        if self.found in ['attr_param', 'start_tag_attr', 'end_tag_attr', 'equal_delim', 'attr_value_start_delim', 'attr_delim']:
            c_chars = c_chars + '>'
        elif self.found == 'attr_value_end_delim':
            c_chars = c_chars + '>'

            possible_delim = self._sink[self._sink.index(self.trace) - 1]
            if possible_delim in hack_actions.MASTER_CONTROL_CHARS and possible_delim != '=':
                c_chars = possible_delim + c_chars
        elif self.found in ['attr_value']:
            c_chars = c_chars + '>'

            possible_delim = self._sink[self._sink.index(self.trace) - 1]
            if possible_delim in hack_actions.MASTER_CONTROL_CHARS and possible_delim != '=':
                c_chars = possible_delim + c_chars

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

if __name__ == '__main__':
    sink = u"<img src=popup=1;><imgabcdef"
    parser = CustomHTMLParser('abcdef')
    parser.feed(sink)
    print(sink)
    print(parser.get_control_chars())
    print(parser.get_stack())
    print(parser.get_attrs())
    print(parser.get_context())
