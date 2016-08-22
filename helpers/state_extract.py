import os
import sys
import json
import random
import logging

from ..browser import NBrowser
from ..utilities import clean_placeholder


class DummyState(object):
    def __init__(self):
        self.elements = []

    def __str__(self):
        s = ''
        for e in self.elements:
            s += str(e)
        return(s)


class DummyElement(object):
    def __init__(self, tag=None, placeholder=None, interacted=False):
        self.tag = tag
        self.placeholder = placeholder
        self.interacted = interacted
        self.children = []

    def __str__(self):
        child_s = ''
        for c in self.children:
            child_s = child_s + ',' + str(c)
        return('TAG: %s Placeholder: %s Interacted: %s  (%s)' % (self.tag, self.placeholder, str(self.interacted), child_s))


if __name__ == "__main__":
    STATEINFO_DIR = sys.argv[1]
    # logging.basicConfig(format='%(asctime)s : %(levelname)s : %(message)s', level=logging.INFO)
    browser = NBrowser()
    for (dirpath, dirnames, filenames) in os.walk(STATEINFO_DIR):
        for file in filenames:
            with open(os.path.join(dirpath, file), 'r') as f:
                data = json.loads(f.read())
            if len(data):
                state = DummyState()
                for e in data:
                    if e.get('children', None) and e['tag'] == 'form':
                        form = DummyElement(tag='form', interacted=random.choice([True, False]))
                        for elem in e['children']:
                            if elem.get('placeholder', None):
                                placeholder = clean_placeholder(elem['placeholder'])
                                if placeholder:
                                    placeholder = placeholder.encode('utf-8')
                                    form.children.append(DummyElement(
                                        tag=elem['tag'],
                                        placeholder=placeholder))
                        state.elements.append(form)
                    elif e.get('placeholder', None) and e['tag'] == 'a':
                        placeholder = clean_placeholder(e['placeholder'])
                        if placeholder:
                            placeholder = placeholder.encode('utf-8')
                            state.elements.append(DummyElement(
                                tag=e['tag'],
                                placeholder=placeholder,
                                interacted=random.choice([True, False])))
                print(state)
                vector, elements = browser.get_state_vector(state=state)
                print(vector)
                print('\n\n\n')
    browser.close()
