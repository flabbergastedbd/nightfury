import re
import labels
import random
import string
import config
import help2vec

from pattern.en import parsetree, pprint, singularize, wordnet
from selenium.common.exceptions import InvalidSelectorException, NoSuchElementException

def get_element_xpath(elem):
    if elem and elem.get_attribute("id"):
        return('//*[@id="%s"]' % (elem.get_attribute("id")))
    else:
        return get_element_tree_xpath(elem)

def get_element_tree_xpath(elem):
    paths = []
    while (elem and elem.get_attribute("nodeType") == '1'):
        index = len(get_previous_siblings(elem))
        tag_name = elem.get_attribute("nodeName").lower()
        path_index = '[%d]' % (index + 1) if index else ""
        paths = [tag_name + path_index] + paths
        elem = get_parent_element(elem)
    return('/%s' % ('/'.join(paths)) if len(paths) else None)

def get_parent_element(elem):
    try:
        elem = elem.find_element_by_xpath('..')
    except InvalidSelectorException:
        elem = None
    return(elem)

def get_previous_siblings(elem):
    try:
        elems = elem.find_elements_by_xpath('preceding-sibling::%s' % (elem.get_attribute('nodeName')))
    except InvalidSelectorException:
        elems = []
    return(elems)

def get_placeholder(driver, elem):
    placeholder = None
    if elem.get_attribute("placeholder"):
        placeholder = elem.get_attribute("placeholder")

    try:
        if elem.get_attribute("id") and driver.find_element_by_xpath('//label[@for="%s"]' % (elem.get_attribute("id"))):
            placeholder = driver.find_element_by_xpath('//label[@for="%s"]' % (elem.get_attribute("id"))).get_attribute("innerHTML")
            placeholder = placeholder.strip('-: ')
    except NoSuchElementException:
        pass
    return(clean_html_tags(placeholder) if placeholder else None)

def clean_html_tags(text):
    text = re.sub(re.compile(r'<[^>]+?>', re.MULTILINE), '', text)
    return(text)

def get_pe_dict(elems):
    """
    Return {placeholder.lower(): element, placeholder.lower(): element, ....}
    """
    placeholders = {}
    for i in elems:
        if i.tag == "input" and i.type not in config.NON_TEXT_INPUT_TYPES and i.placeholder:
            placeholders[i.placeholder.lower()] = i
        elif i.tag == "form":
            placeholders.update(get_pe_dict(i.children))
    return(placeholders)

def match_help_to_element_NLP(elements, text):
    placeholder_elements_dict = get_pe_dict(elements)
    placeholders = placeholder_elements_dict.keys()
    t = parsetree(text)
    # pprint(t)
    for sen in t:
        chunks = filter(lambda x: (x.type == 'NP'), sen.chunks)
        for chunk in chunks:
            words = filter(lambda x: (x.type.startswith('NN')), chunk.words)
            for w in words:
                for p in placeholders:
                    p = parsetree(p)
                    p_words = [i.string for i in p.words]
                    if w.string.lower() in p_words:
                        return(placeholder_elements_dict[p])
    return(None)

def match_help_to_element_visually(elements, location, size):
    """
    Assumes that help text is below or right side of the input
    """
    X_THRESHOLD = (config.BROWSER_WIDTH / 100) * 4
    Y_THRESHOLD = (config.BROWSER_HEIGHT / 100) * 2
    for e in elements:
        if e.tag == 'input' and e.type not in config.NON_TEXT_INPUT_TYPES and not e.help:
            if len(range(e.location_y,  e.location_y + e.size_h, Y_THRESHOLD) and \
                    range(location["y"], location["y"] + size["height"], Y_THRESHOLD)) and \
                    0 < ((location["x"] + size["width"]/2) - (e.location_x + e.size_w/2)) < 1.5*e.size_w:
                return(e)
            elif len(range(e.location_x,  e.location_x + e.size_w, X_THRESHOLD) and \
                    range(location["x"], location["x"] + size["width"], X_THRESHOLD)) and \
                    0 < ((location["y"] + size["height"]/2) - (e.location_y + e.size_h/2)) < 1.5*e.size_h:
                return(e)
        elif e.tag == "form":
            found_e = match_help_to_element_visually(e.children, location, size)
            if found_e: return(found_e)

def get_alternate_char(c):
    ac = ''
    if 48 <= ord(c) <= 57:
        ac = random.choice(list(string.digits))
    elif 65 <= ord(c) <= 90:
        ac = random.choice(list(string.uppercase))
    elif 97 <= ord(c) <= 122:
        ac = random.choice(list(string.lowercase))
    else: # Special characters
        ac = c
    return(ac)

def get_input_value(e, all_e):
    payload = ''
    if e.vector:
        payload = help2vec.input_vec_to_string(e.vector)
    elif e.label:
        payload = labels.get_payload_for_label(e.label) or ''
    if e.type and (not payload or not test_html5_input_type_payload(e.type, payload)):
        payload = get_html5_input_type_payload(e) or payload
    if e.maxlength and len(payload) > e.maxlength:
        payload = payload[:e.maxlength]
    return(payload)

def test_html5_input_type_payload(input_type, payload):
    if input_type == "number":
        return(re.match('^[0-9]+$', payload))
    elif input_type == "text":
        return(re.match('^.+$', payload))
    elif input_type == "email":
        return(re.match('^[^@]+@[a-z0-9\.]+$', payload))
    else:
        return(False)

def get_html5_input_type_payload(e):
    input_type = e.type
    payload = ''
    if input_type == "number":
        payload = ''.join([get_alternate_char('9') for i in range(0, 10)])
    elif input_type == "text":
        payload = ''.join([get_alternate_char('x') for i in range(0, 10)])
    elif input_type == "email":
        payload = config.EMAIL_INPUT
    return(payload)
