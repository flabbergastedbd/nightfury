import re
import hack_actions

from HTMLParser import HTMLParser

class CustomHTMLParser(HTMLParser):
    def __init__(self, taint):
        self.stack = []
        self.found_in_tag_attr_param = False
        self.found_in_tag_attr_value = False
        self.found_in_tag_name = False
        self.found_in_data = False
        self.taint = taint
        self.trace = ''
        HTMLParser.__init__(self)

    @property
    def found(self):
        return(self.found_in_tag_name or self.found_in_tag_attr_param or self.found_in_tag_attr_value or self.found_in_data)

    def get_context(self):
        c = ''
        if self.found_in_tag_attr_param:
            c = 'attr_param'
        elif self.found_in_tag_attr_value:
            c = 'attr_value'
        elif self.found_in_tag_name:
            c = 'tag_name'
        elif self.found_in_data:
            c = 'data'
        return(c)

    def feed(self, data):
        self._sink = data
        HTMLParser.feed(self, data)

    def get_stack(self):
        return(self.stack)

    def handle_starttag(self, tag, attrs):
        if self.found == False:
            if tag != 'div':
                self.stack.append(tag)
                if self.taint in tag:
                    self.found_in_tag_name = True
            for param, value in attrs:
                if self.taint in param:
                    self.found_in_tag_attr_param = True
                    self.trace = param
                elif value and self.taint in value:
                    self.found_in_tag_attr_value = True
                    self.trace = value

    def handle_endtag(self, tag):
        if self.found == False:
            if len(self.stack) > 0 and self.stack[-1] == tag:
                self.stack.pop()

    def handle_data(self, data):
        if self.found == False:
            if self.taint in data:
                self.trace = data
                self.found_in_data = True

    def get_control_chars(self):
        c_chars = ''
        if self.found_in_tag_attr_param:
            c_chars = c_chars + '>'
        elif self.found_in_tag_attr_value:
            c_chars = c_chars + '>'

            c_chars = self._sink[self._sink.index(self.trace) - 1] + c_chars

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
    sink = u'<title><alert()</title>'
    parser = CustomHTMLParser('alert()')
    parser.feed(sink)
    print(parser.get_control_chars())
    print(parser.get_stack())
