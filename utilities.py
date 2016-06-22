import re
import labels
import random
import string
import config
import help2vec

from pattern.en import parsetree, pprint, singularize, wordnet
from selenium.common.exceptions import InvalidSelectorException, NoSuchElementException

PRINTABLE_CHARS = set(string.printable)

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

def get_strings(driver):
    strings = {}
    for s in driver.find_element_by_tag_name('body').text.splitlines():
        try:
            elem = driver.find_element_by_xpath("//*[text()='%s']" % (s))
            if elem.is_displayed():
                strings[s] = elem
        except NoSuchElementException:
            pass
    return(strings)

def get_placeholder(driver, elem):
    # import pdb
    # pdb.set_trace()
    placeholder = None
    """
    for s, e in strings.items():
        ax1, bx1 = e.location['x'], elem.location['x']
        ax2, bx2 = ax1 + e.size['width'], bx1 + elem.size['width']
        axl, bxl = e.size['width'], elem.size['width']
        axc, bxc = (ax1 + ax2)/2, (bx1 + bx2)/2
        ay1, by1 = e.location['y'], elem.location['y']
        ay2, by2 = ay1 + e.size['height'], by1 + elem.size['height']
        ayl, byl = e.size['height'], elem.size['height']
        ayc, byc = (ay1 + ay2)/2, (by1 + by2)/2
        # Check if area overlaps
        plain_overlap_area = (max(0, min(ax2, bx2) - max(ax1, bx1))*max(0, min(ay2, by2) - max(ay1, by1)))
        if plain_overlap_area and plain_overlap_area/(axl*ayl) == 1:
            placeholder = s
            break

    if not placeholder:
        for s, e in strings.items():
            ax1, bx1 = e.location['x'], elem.location['x']
            ax2, bx2 = ax1 + e.size['width'], bx1 + elem.size['width']
            axl, bxl = e.size['width'], elem.size['width']
            axc, bxc = (ax1 + ax2)/2, (bx1 + bx2)/2
            ay1, by1 = e.location['y'], elem.location['y']
            ay2, by2 = ay1 + e.size['height'], by1 + elem.size['height']
            ayl, byl = e.size['height'], elem.size['height']
            ayc, byc = (ay1 + ay2)/2, (by1 + by2)/2
            if abs(ayc - byc) < 1.5*ayl and abs(axc - bxc) < 1.5*axl:  # Align on horizontal axis, so use y coordinates
                placeholder = s
                break
    return(clean_html_tags(placeholder.strip('-: ')) if placeholder else None)
    """
    if elem.get_attribute('nodeName').lower() == 'a':
        placeholder = elem.text
    else:
        # Get placeholder attribute directly
        if elem.get_attribute("placeholder"):
            placeholder = elem.get_attribute("placeholder")

        # Get placeholder attribute directly
        if not placeholder and elem.get_attribute("aria-label"):
            placeholder = elem.get_attribute("aria-label")

        # Try finding a label element
        if not placeholder:
            try:
                if elem.get_attribute("id") and driver.find_element_by_xpath('//label[@for="%s"]' % (elem.get_attribute("id"))):
                    placeholder = driver.find_element_by_xpath('//label[@for="%s"]' % (elem.get_attribute("id"))).get_attribute("innerHTML")
            except NoSuchElementException:
                try:
                    if elem.get_attribute("name") and driver.find_element_by_xpath('//label[@for="%s"]' % (elem.get_attribute("name"))):
                        placeholder = driver.find_element_by_xpath('//label[@for="%s"]' % (elem.get_attribute("name"))).get_attribute("innerHTML")
                except NoSuchElementException:
                    pass

        # Try finding a column previous to this
        if not placeholder:
            try:
                parent_elem = get_parent_element(elem)
                if parent_elem and parent_elem.get_attribute('nodeName').lower() == 'td':
                    parent_siblings = get_previous_siblings(parent_elem)
                    for i in reversed(parent_siblings):
                        if not placeholder and len(i.text.strip('-: ')) > 0:
                            placeholder = i.text
                            break
            except NoSuchElementException:
                pass
    return(clean_placeholder(placeholder))

def clean_placeholder(placeholder):
    return(clean_html_tags(clean_non_printable_chars(placeholder.strip('-: \n\t'))) if placeholder else None)

def clean_html_tags(text):
    text = re.sub(re.compile(r'<[^>]+?>', re.MULTILINE), '', text)
    return(text)

def clean_non_printable_chars(text):
    return(filter(lambda x: x in PRINTABLE_CHARS, text))

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
                    p_t = parsetree(p)
                    p_words = [i.string for i in p_t.words]
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
    if e.help_vector:
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

def is_element_mandatory(placeholder):
    if placeholder and '*' in placeholder:
        return(True)
    return(False)
