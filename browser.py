import os
import sys
import json
import uuid
import time
import config
import random
import shutil
import difflib
import help2vec
import utilities
import numpy as np
import networkx as nx
import traceback
import labels
import agent
import logging
import collections

from fuzzywuzzy import fuzz
from rlpy.Domains.Domain import Domain
from selenium import webdriver
from selenium.webdriver.remote.remote_connection import LOGGER
from selenium.webdriver.common.proxy import Proxy, ProxyType
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker, backref
from sqlalchemy import Table, Column, Integer, String, Boolean,\
            Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property, hybrid_method
from selenium.common.exceptions import InvalidSelectorException, NoSuchElementException
from selenium.webdriver import ActionChains
from selenium.webdriver.common.keys import Keys
from n_exceptions import *
from IPython.core.debugger import Tracer

Base = declarative_base()

state_element_association_table = Table('state_element_association', Base.metadata,
    Column('state_id', Integer, ForeignKey('dom_states.id', ondelete="CASCADE")),
    Column('element_id', Integer, ForeignKey('dom_elements.id', ondelete="CASCADE"))
)

class DomState(Base):
    __tablename__ = "dom_states"
    id = Column(Integer, primary_key=True)
    dom = Column(Text)
    text = Column(Text)
    url = Column(String)
    seed = Column(String)
    absolute = Column(Boolean, default=False)
    nlp_analysis = Column(Boolean, default=False)
    screenshot = Column(String)
    ssim_minimum = Column(Float, default=0.99)

    def __str__(self):
        return("ID: %d ABSOLUTE: %s URL: %s" % (self.id, self.absolute, self.url))

class DomElement(Base):
    __tablename__ = "dom_elements"
    id = Column(Integer, primary_key=True)
    parent_id = Column(Integer, ForeignKey('dom_elements.id'))
    tag = Column(String)
    placeholder = Column(String, nullable=True)
    label = Column(String, nullable=True)
    help_vector_string = Column(String)
    xpath = Column(String)
    help = Column(String, nullable=True)
    value = Column(String, nullable=True)
    maxlength = Column(Integer, nullable=True)
    type = Column(String, nullable=True)
    name = Column(String, nullable=True)
    location_x = Column(Integer)
    location_y = Column(Integer)
    size_w = Column(Integer)
    size_h = Column(Integer)
    parent = relationship("DomElement", backref="children", remote_side=[id])
    interacted = Column(Boolean, default=False)
    dom_states = relationship("DomState",
        secondary=state_element_association_table,
        backref=backref("elements", order_by="DomElement.placeholder"),
        order_by="DomState.id")

    def __str__(self):
        return("Tag: %s Placeholder: %s Label: %s Xpath: %s Location: (%d, %d) Size: %d width, %d height)" % (
            self.tag, self.placeholder, self.label, self.xpath, self.location_x, self.location_y, self.size_w, self.size_h))

    @hybrid_property
    def help_vector(self):
        return(json.loads(self.help_vector_string) if self.help_vector_string else None)

    @hybrid_property
    def mandatory(self):
        if (self.placeholder and '*' in self.placeholder) or self.help_vector_string:
            return(True)
        else:
            return(False)

SITE_RESPONSE_SLEEP = 3

class NBrowser(Domain):
    DB_PATH = 'states.db'
    GRAPH_PATH = 'states.graphml'
    def __init__(self):
        self._init_selenium_driver()
        self._init_sqlalchemy_session()
        self._init_networkx_graph()

        self.seed = uuid.uuid4().hex[:5]
        self._current_state_id = 0
        self._input_labeler = labels.InputLabeler()


        # Do RLPY Specific stuff
        self._init_rlpy_variables()
        super(NBrowser, self).__init__()
        self.s0()

    def _init_selenium_driver(self):
        LOGGER.setLevel(logging.WARNING)

        # CHROMEDRIVER_BIN = '/usr/local/bin/chromedriver'
        # os.environ['webdriver.chrome.driver'] = CHROMEDRIVER_BIN
        # self.d = webdriver.Chrome(CHROMEDRIVER_BIN)

        # firefox_profile = webdriver.FirefoxProfile()
        # firefox_profile.set_preference("network.proxy.type", 1)
        # firefox_profile.set_preference("network.proxy.http", '127.0.0.1') #set your ip
        # firefox_profile.set_preference("network.proxy.http_port", 8080) #set your port
        # self.d = webdriver.Firefox(firefox_profile=firefox_profile)
        self.d = webdriver.Firefox()
        # self.d.implicitly_wait(1)

        # self.d = webdriver.PhantomJS(service_args=[
        #     '--proxy=127.0.0.1:8080',
        #     '--proxy-tpe=http'])
        self.d.set_window_size(config.BROWSER_WIDTH, config.BROWSER_HEIGHT)

    def _init_sqlalchemy_session(self):
        # self.engine = create_engine("sqlite:///" + self.DB_PATH)
        self.engine = create_engine("postgresql+psycopg2://nightfury:nightfury@127.0.0.1:5432/states")
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        self.scoped_factory = scoped_session(self.session_factory)
        self.session = self.scoped_factory()

    def _init_networkx_graph(self):
        if os.path.exists(self.GRAPH_PATH):
            self.DG = nx.read_graphml(self.GRAPH_PATH, node_type=int)
        else:
            self.DG = nx.DiGraph()

    def _init_rlpy_variables(self):
        self.LABEL_DIM = self._input_labeler.get_num_labels()
        self.FORM_N = config.STATE_FORM_N
        self.LINK_N = config.STATE_LINK_N

        state_d2v_dim = config.STATE_D2V_DIM
        self.statespace_limits = np.array([[-1, 1] for i in range(0, state_d2v_dim)] +
                [[0, 1] for i in range(0, self.LABEL_DIM)])
        self.continuous_dims = [i for i in range(0, state_d2v_dim)]
        self.DimNames = ['D2V']*state_d2v_dim + ['Label']*self.LABEL_DIM
        self.episodeCap = 5
        self.actions_num = self.FORM_N + self.LINK_N
        self.discount_factor = 0.6

    def s0(self):
        self.reset(hard=True)
        self.navigate_to_url('http://127.0.0.1:8000')
        self.enhance_state_info()

    def navigate_to_url(self, url):
        self.d.get(url)
        self.save_state()

    def navigate_to_state(self, state_id):
        state_obj = self.session.query(DomState).get(state_id)
        if state_obj and state_obj.absolute:
            self.navigate_to_url(state_obj.url)

    def get_current_state(self):
        return(self.get_state(self._current_state_id))

    def get_state(self, id):
        return(self.session.query(DomState).get(id))

    def _get_dom_diff(self):
        """
        Gets diff of DOM between the present state and state mentioned in _current_state_id
        """
        d = difflib.Differ()
        diff = list(d.compare(
            utilities.clean_html_tags(self.get_current_state().text).splitlines(),
            utilities.clean_html_tags(self.d.find_element_by_tag_name('body').text).splitlines()))
        diff = filter(lambda x: x.startswith('+ '), diff)
        diff = [i[2:] for i in diff]
        with open('/tmp/diff.txt', 'w') as f:
            f.write('\n'.join(diff).encode('utf-8'))
        return(diff)

    def _check_if_duplicate_state(self, new_state_obj):
        """
        This is going to be a big ass method to compare two states in lots of ways
        """
        match = False
        for old_state_obj in self.session.query(DomState).all():
            # Lots of IF-Else conditions in order
            if old_state_obj.url != new_state_obj.url:
                match = False
            ssim = utilities.image_ssim(old_state_obj.screenshot, new_state_obj.screenshot)
            if ssim > old_state_obj.ssim_minimum:
                logging.debug("State matched using SSIM of %f (%s, %s)" % (ssim, old_state_obj.screenshot, new_state_obj.screenshot))
                match = True
            if match == True:
                return(old_state_obj)
        return(None)

    def _check_if_duplicate_form(self, form, temp_form_inputs):
        query = self.session.query(DomElement).filter_by(xpath=form.xpath)
        dup_form = query.first()
        if dup_form and len(dup_form.children) == len(temp_form_inputs):  # If match then check input by input
            dup_form_children = self.session.query(DomElement).filter_by(parent_id=dup_form.id)
            for i in temp_form_inputs:
                if ((i.placeholder and not dup_form_children.filter_by(placeholder=i.placeholder).first()) or \
                    (i.name and not dup_form_children.filter_by(name=i.name).first())):
                    dup_form = None
                    break
        else:
            dup_form = None
        return(dup_form)

    def _check_if_duplicate_element(self, new_elem_obj):
        """
        This is going to be a big ass method to compare two elements in lots of ways
        """
        elem = None
        if self.session.query(DomElement).count() > 0:
            query = self.session.query(DomElement)
            if new_elem_obj.placeholder:
                query = query.filter_by(tag=new_elem_obj.tag, placeholder=new_elem_obj.placeholder)
            else:
                query = query.filter_by(
                    name=new_elem_obj.name,
                    location_x=new_elem_obj.location_x,
                    location_y=new_elem_obj.location_y,
                    size_w=new_elem_obj.size_w,
                    size_h=new_elem_obj.size_h)
            elem = query.first()
        return(elem)

    def _construct_current_state(self):
        logging.info('Constructing the current state as object')
        new_state_obj = DomState(
            dom=self.d.execute_script("return document.documentElement.outerHTML;"),
            text=self.d.find_element_by_tag_name('body').text,
            url=self.d.current_url,
            absolute=False if self.get_current_state() and self.d.current_url == self.get_current_state().url else True,
            screenshot=os.path.join("command_cache", uuid.uuid4().hex[:10] + ".png"),
            seed=self.seed,
        )
        self.d.save_screenshot(new_state_obj.screenshot)
        logging.info('Completed constructing the current state as object')
        state = self._check_if_duplicate_state(new_state_obj)
        if state:
            elements = state.elements
            self._current_state_id = state.id
            logging.info("State already found as %d" % (state.id))
            new = False
        else:
            elements = self.get_current_elements()
            state = self._add_state(new_state_obj, elements)
            self.DG.add_node(state.id, url=state.url, absolute=state.absolute, seed=self.seed)
            self._current_state_id = state.id
            logging.info("Adding new state as no existing matched (ID: %d Absolute: %s URL : %s)" % (state.id, state.absolute, state.url))
            new = True
        return(state, elements, new)

    def _construct_state_vector(self, state, labels=None):
        forms = collections.OrderedDict()
        links = collections.OrderedDict()
        for e in state.elements:
            if e.tag == 'form':
                placeholders = []
                for c in e.children:
                    if c.placeholder: placeholders.append(c.placeholder)
                if placeholders:
                    if e.interacted: placeholders.append('filled')
                    forms[e] = placeholders
            elif e.tag == 'a':
                if e.placeholder:
                    placeholder = [e.placeholder]
                    if e.interacted: placeholder += ['clicked']
                    links[e] = placeholder
        if labels == None:
            labels = collections.OrderedDict()
            for label in self._input_labeler.get_labels():
                if self.session.query(DomElement).filter_by(label=label).filter(DomElement.value != None).first():
                    labels[label] = 1.0
        state_words = []
        elements = []
        for i in range(0, self.FORM_N):
            try:
                form = forms.items()[i]
                state_words += form[1]
                elements.append(form[0])
            except IndexError:
                # state_words = np.concatenate((state_words, np.zeros(self.FORM_DIM)))
                elements.append(None)
        for i in range(0, self.LINK_N):
            try:
                link = links.items()[i]
                state_words += link[1]
                elements.append(link[0])
            except IndexError:
                # state_words = np.concatenate((state_words, np.zeros(self.LINK_DIM)))
                elements.append(None)
        state_words += labels.keys()
        return(self.agent.d2v(state_words), elements)

    def save_state(self):
        """
        At this point the current state points to previous state as browser just entered a new state
        Now we will save this if it is a previously undiscovered state.
        """
        logging.debug("Trying to save this state if this is previously undetected")
        return(self._construct_current_state()[2])

    def _add_state(self, state, elements):
        self.session.merge(state) if state.id else self.session.add(state)
        for e in elements:
            e.dom_states.append(state)
            self.session.merge(e) if e.id else self.session.add(e)
        self.session.commit()
        return(state)

    def close(self):
        """
        A method to cleanly close everything
        """
        nx.write_graphml(self.DG, path=self.GRAPH_PATH)
        self.session.close()
        if self.agent:
            self.agent.close()
        # Keep webdriver for end, because it might have errors
        self.d.quit()

    def get_current_elements(self):
        logging.info('Getting current element objects')
        elements = []
        # strings = utilities.get_strings(self.d)
        # import pdb
        # pdb.set_trace()
        logging.debug('Iterating over form and its elements to create objects')
        for f in self.d.find_elements_by_tag_name('form'):
            temp_form_inputs = []
            for i in f.find_elements_by_tag_name('input') + f.find_elements_by_tag_name('select'):
                if i.is_displayed():
                    elem_obj = DomElement(
                        tag=i.get_attribute('nodeName').lower(),
                        xpath=utilities.get_element_xpath(i),
                        help=None,
                        value=None,
                        maxlength=int(i.get_attribute('maxlength')) if i.get_attribute('maxlength') else None,
                        type=i.get_attribute('type'),
                        name=i.get_attribute('name'),
                        location_x=i.location["x"],
                        location_y=i.location["y"],
                        size_w=i.size["width"],
                        size_h=i.size["height"],
                    )

                    # Now get the placeholder and its label
                    input_placeholder = utilities.get_placeholder(self.d, i)
                    if input_placeholder:
                        elem_obj.placeholder = input_placeholder
                    # Label for placeholder
                    if input_placeholder and elem_obj.type not in config.NON_TEXT_INPUT_TYPES:
                        elem_obj.label = self._input_labeler.get_label(input_placeholder)

                    # Add input obj
                    temp_form_inputs.append(elem_obj)

            if len(temp_form_inputs) > 0:
                temp_form_element = DomElement(
                    tag='form',
                    xpath=utilities.get_element_xpath(f),
                )
                # Now add form and element objects after checking for duplicates
                form_element = self._check_if_duplicate_form(temp_form_element, temp_form_inputs)
                if form_element:
                    logging.debug("Duplicate form detected (ID: %d) --> %s" % (form_element.id, str([k.placeholder for k in temp_form_inputs])))
                    elements.append(form_element)
                    elements += form_element.children
                else:  # If form is not detected as duplicate just blindly add all inputs
                    elements.append(temp_form_element)
                    for i in temp_form_inputs:
                        i.parent = temp_form_element
                        elements.append(i)
                temp_form_inputs = []
        logging.debug('Iterating over links to create objects')
        for i in self.d.find_elements_by_tag_name('a'):
            if i.is_displayed():
                elem_obj = DomElement(
                    tag=i.get_attribute('nodeName').lower(),
                    xpath=utilities.get_element_xpath(i),
                    help=None,
                    value=None,
                    maxlength=int(i.get_attribute('maxlength')) if i.get_attribute('maxlength') else None,
                    type=i.get_attribute('type'),
                    name=i.get_attribute('name'),
                    location_x=i.location["x"],
                    location_y=i.location["y"],
                    size_w=i.size["width"],
                    size_h=i.size["height"],
                    placeholder=utilities.get_placeholder(self.d, i),
                )
                duplicate_obj = self._check_if_duplicate_element(elem_obj)
                if duplicate_obj:
                    logging.debug("Duplicate object for %s (ID: %d)" % (str(elem_obj.placeholder), duplicate_obj.id))
                else:
                    self.session.add(elem_obj)
                    logging.debug("Brand new element %s (xpath=%s)" % (str(elem_obj.placeholder), elem_obj.xpath))
                elements.append(duplicate_obj) if duplicate_obj else elements.append(elem_obj)
        logging.debug('%d Elements gathered' % (len(elements)))
        return(elements)

    def _update_element(self, e, state_id=None):
        self.session.merge(e)
        self.session.commit()

    def _update_state(self, state_obj):
        self.session.merge(state_obj)
        self.session.commit()
        return(state_obj)

    def _enhance_element_info(self, sen, elements):
        lower_sen = sen.lower()
        lower_placeholder_set_ratio = []
        for i in elements:
            if i.placeholder:
                lower_placeholder_set_ratio.append(fuzz.token_set_ratio(i.placeholder.lower(), lower_sen))
        vec = help2vec.input_help_to_vec(lower_sen)
        enhanced = False or (len(lower_placeholder_set_ratio) > 0 and max(lower_placeholder_set_ratio) > 50)
        if len(vec) > 0:  # Means it might be a help text. Now we have to link this with the corresponding input
            logging.debug("Following sentence was detected as input help")
            logging.debug("Sentence: %s" % (sen))
            logging.debug("Vector: %s" % (str(vec)))
            e = utilities.match_help_to_element_NLP(elements, lower_sen)
            if e and not e.help:  # We found reference to a placeholder so fine.
                logging.debug("Found following element for input help by placeholder reference")
                logging.debug("Element: %s" % (str(e)))
                e.help = sen
                e.help_vector_string = json.dumps(vec)
                self._update_element(e)
                enhanced = True
            else: # We couldn't find reference to placeholder. So visual correlation
                try:  # Check if element still exists
                    elem = self.d.find_element_by_xpath("//*[contains(text(), '%s')]" % (sen))
                    if elem:
                        e = utilities.match_help_to_element_visually(elements, elem.location, elem.size)
                        if e and not e.help:  # We found reference to a placeholder so fine.
                            logging.debug("Found following element for input help by visual reference")
                            logging.debug("Element: %s" % (str(e)))
                            e.help = sen
                            e.help_vector_string = json.dumps(vec)
                            self._update_element(e)
                            enhanced = True
                except InvalidSelectorException, NoSuchElementException:
                    pass
        return(enhanced)

    def enhance_state_info(self):
        """
        !!! Takes a lot of time, only call when a form needs to be filled
        + Tries to process all text present in the DOM
        + Finds senntences which might be help statements
            + Tries finding if it is mentioning a label
            + Visually relate the help text and input
        """
        if self.get_current_state().nlp_analysis == False:
            logging.debug("Information will now be extracted from this state")
            for sen in self.get_current_state().text.splitlines():
                elements = self.get_current_state().elements
                self._enhance_element_info(sen, elements)
            current_state = self.get_current_state()
            current_state.nlp_analysis = True
            current_state = self._update_state(current_state)
        else:
            logging.debug("Information is already extracted from this state")

    def _reset_action_history(self):
        logging.info("Resetting action history")
        self._action_history = []

    def reset(self, hard=True):
        if hard == True:
            logging.info("Cleaning all data in state db")
            self.session.query(DomElement).delete()
            self.session.query(DomState).delete()
            self.session.commit()
        self._reset_action_history()

    def _add_action_history(self, element):
        logging.info("Adding element xpath to action history (%s)" %(element.xpath))
        self._action_history.append(element.xpath)

    def _am_i_struck_in_loop(self):
        struck = False
        if len(self._action_history) > 1 and self._action_history[-1] == self._action_history[-2]:
            logging.info("Detected same action in two successive trails, so struck")
            struck = True
        return(struck)

    def _ask_user(self, elements):
        for i, e in enumerate(elements):
            if e: print("%2d) %s [xpath=%s]" % (i, str(e.placeholder), str(e.xpath)))
        print('\n')
        return(int(raw_input('Select an action index > ')))

    def step(self, a):
        # Save some variables
        old_num_states = self.session.query(DomState).count()
        observation = self._custom_step(a)
        new_num_states = self.session.query(DomState).count()
        if new_num_states > old_num_states:
            observation[2] = 10
        else:
            observation[2] = -4
        return(observation)

    def _custom_step(self, action_index):
        state = self.get_current_state()
        state_vector, elements = self._construct_state_vector(state)
        state_vector = state_vector.tolist()
        self.act_on(elements[action_index])
        if self.save_state(): self.enhance_state_info()
        new_state = self.get_current_state()
        new_state_vector, new_elements = self._construct_state_vector(new_state)
        new_state_vector = new_state_vector.tolist()
        return([None, new_state_vector, False, self._non_none_indices(new_elements)])  # Reward is None, which will be filled and fed to train

    def isTerminal(self):
        return(False)

    def possibleActions(self):
        """
        Called to get the list of indices of possible actions of current state
        """
        state = self.get_current_state()
        state_vector, elements = self._construct_state_vector(state)
        return(self._non_none_indices(elements))

    @staticmethod
    def _non_none_indices(l):
        return([i for i, e in enumerate(l) if e != None])

    def act_on(self, element):
        # Save few values for reward calculation
        if element.tag == 'form':
            self.fill_form(element)
        elif element.tag == 'a':
            self.click_link(element)
        time.sleep(SITE_RESPONSE_SLEEP)

    def click_link(self, element):
        try:
            logging.info("Trying to click %s" % (str(element.placeholder)))
            selenium_elem = self.d.find_element_by_xpath(element.xpath)
            selenium_elem.click()
            element.interacted = True
            self._update_element(element)
        except NoSuchElementException:
            pass

    def fill_form(self, f_elem, attempt=0):
        elements = []
        values = {}
        form = None
        for i in self.get_current_state().elements:
            if i.xpath == f_elem.xpath:
                form = i
                elements = i.children
                break
        logging.info("Trying to fill form %s" % (form.xpath))
        if attempt < 1:  # Only one attempt
            for e in elements + elements:  # Iterate twice
                d_e = self.d.find_element_by_xpath(e.xpath)
                payload = None
                if e.tag == 'select':
                    s = webdriver.support.ui.Select(d_e)
                    payload = random.choice(s.options).get_attribute('value')
                    s.select_by_value(payload)
                elif e.type == "checkbox" and e.mandatory and d_e.is_selected():
                    d_e.click()
                elif e.type == "radio" and not d_e.is_selected():
                    try:
                        elem = self.d.find_element_by_css_selector("input[name='%s']:checked" % (e.name))
                        payload = ''
                    except NoSuchElementException:
                        d_e.click()
                        payload = d_e.get_attribute("value")
                elif e.type == "submit":
                    pass
                else:
                    value = None
                    same_e = self.session.query(DomElement).filter_by(placeholder=e.placeholder).filter(DomElement.value != None).first()
                    sibling_e = self.session.query(DomElement).filter_by(label=e.label).filter(DomElement.value != None).first()
                    if same_e:
                        value = same_e.value
                    elif sibling_e:
                        value = sibling_e.value
                    else:
                        value = utilities.get_input_value(e, elements)
                    d_e.send_keys(Keys.COMMAND + 'a')
                    d_e.send_keys(value)
                    payload = value
                if payload:
                    logging.info("%s = %s" % (str(e.placeholder), payload))
                    e.value = payload
                    self.session.merge(e)  # Commit only when success
                time.sleep(1)
            if form:
                form.interacted = True
                self.session.merge(form)
                self.d.find_element_by_xpath(form.xpath).submit()
                time.sleep(SITE_RESPONSE_SLEEP)
                if not self._form_fill_success(form):
                    self.navigate_to_state(self._current_state_id)
                    self.fill_form(form, attempt=attempt+1)
                else:
                    self.session.commit()
        else:
            logging.info("Form fill failed multiple times and leaving it. Humse na ho payi!!")
            # Interaction even if failed should be marked
            # self.session.rollback()

    def _form_fill_success(self, form, old_state_id=None):
        diff = self._get_dom_diff()
        new_lines_count = len(diff)
        new_vector_count = 0
        old_input_count = 0
        for line in diff:
            if self._enhance_element_info(line, form.children):
                new_vector_count += 1
        for e in form.children:
            try:
                self.d.find_element_by_xpath(e.xpath)
                old_input_count += 1
            except NoSuchElementException, InvalidSelectorException:
                continue
        if (new_lines_count > 0 and new_vector_count > 0.8 * new_lines_count):
            logging.info("Form fill considered as fail")
            return(False)
        else:
            logging.info("Form fill considered as success")
            return(True)


if __name__ == "__main__":
    try:
        MODE_FILE = '/tmp/nightfury.mode'
        if not os.path.exists(MODE_FILE):
            with open(MODE_FILE, 'w') as f:
                f.write('m')
        b = None
        b = NBrowser()
        # b.navigate_to_url('file:///Users/tunnelshade/Downloads/YodleeLabs-Registration.htm')
        # b.navigate_to_url('https://moneycenter.yodlee.com/moneycenter/mfaregistration.moneycenter.do?_flowId=mfaregistration&c=csit_key%3AVZl14EfWF4rGSHQ1F6NEZWFU%2Bo8%3D&l=_flowId')
        # b.navigate_to_url('http://clin.cmcvellore.ac.in/onlineIPO/Patdetails/Home.aspx')
        # b.navigate_to_url('https://signup.ballparkapp.com/')
        # b.navigate_to_url('https://hujplpiqmu.ballparkapp.com/session/new')
        # b.navigate_to_url('https://twitter.com/signup')
        # b.navigate_to_url('http://dummy:8888')
        b.navigate_to_url('http://127.0.0.1:8000')
        # b.navigate_to_url('http://localhost:8080/WebGoat/login.mvc')
        b.enhance_state_info()
        # raise KeyboardInterrupt()
        # Pre-train
        for i in range(0, 500):  # Experiment number
            try:
                for j in range(0, 5):
                    with open(MODE_FILE, 'r') as f:
                        mode = f.read()
                        if len(mode) > 1: mode = mode[0]
                    if mode == 'p':
                        b.agent.replay()
                        time.sleep(5)
                    else:
                        if mode == 'h':
                            observation = b.ask_agent(human=True)
                        else:
                            observation = b.ask_agent(human=False)
                        b.train_agent(observation)
                        if observation[2] == 10: raise SoftResetEnvironment()  # Terminal state
                if j % 10: raise HardResetEnvironment()
            except (NoElementsToInteract, StruckInLoop, SoftResetEnvironment) as e:
                logging.info(e.message)
                # b.navigate_to_url('http://dummy:8000/delete_everything')  # Custom reset handler built into our webapp
                b.d.get('http://127.0.0.1:8000/accounts/logout/')  # Custom reset handler built into our webapp
                b.reset(hard=False)
                b.navigate_to_url('http://127.0.0.1:8000/')  # Custom reset handler built into our webapp
            except (HardResetEnvironment) as e:
                logging.info(e.message)
                b.d.get('http://dummy:8000/delete_everything')  # Custom reset handler built into our webapp
                b.d.get('http://dummy:8000/accounts/logout/')  # Custom reset handler built into our webapp

                b.reset(hard=True)
                b.navigate_to_url('http://127.0.0.1:8000/')  # Custom reset handler built into our webapp
                """
                b.d.get('http://localhost:8080/WebGoat/j_spring_security_logout')  # Custom reset handler built into our webapp
                b.reset(hard=True)
                time.sleep(SITE_RESPONSE_SLEEP)
                """
        # Tracer()()
    except KeyboardInterrupt:
        pass
    except Exception, e:
        print(traceback.print_exc())
    finally:
        if b: b.quit()
