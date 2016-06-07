import os
import json
import uuid
import time
import config
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
from skimage.measure import compare_ssim as ssim
from scipy.misc import imread
from selenium import webdriver
from selenium.webdriver.remote.remote_connection import LOGGER
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy import Table, Column, Integer, String, Boolean,\
            Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property, hybrid_method
from selenium.common.exceptions import InvalidSelectorException, NoSuchElementException
from selenium.webdriver import ActionChains
from selenium.webdriver.common.keys import Keys


Base = declarative_base()

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
    ssim_minimum = Column(Float, default=0.95)

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
    dom_state_id = Column(Integer, ForeignKey("dom_states.id"))
    dom_state = relationship("DomState", backref="elements")

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


class NBrowser(object):
    DB_PATH = 'states.db'
    GRAPH_PATH = 'states.graphml'
    def __init__(self):
        self._init_logging()
        self._init_selenium_driver()
        self._init_sqlalchemy_session()
        self._init_networkx_graph()

        self.seed = uuid.uuid4().hex[:5]
        self._current_state_id = 0
        self._input_labeler = labels.InputLabeler()

        self._init_agent()

    def _init_logging(self):
        logger = logging.getLogger()
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)8s] --- %(message)s (%(filename)s:%(lineno)s)",
            "%H:%M")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

    def _init_selenium_driver(self):
        LOGGER.setLevel(logging.WARNING)
        self.d = webdriver.Firefox()
        self.d.implicitly_wait(1)
        self.d.set_window_size(config.BROWSER_WIDTH, config.BROWSER_HEIGHT)

    def _init_sqlalchemy_session(self):
        self.engine = create_engine("sqlite:///" + self.DB_PATH)
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        self.scoped_factory = scoped_session(self.session_factory)
        self.session = self.scoped_factory()

    def _init_networkx_graph(self):
        if os.path.exists(self.GRAPH_PATH):
            self.DG = nx.read_graphml(self.GRAPH_PATH, node_type=int)
        else:
            self.DG = nx.DiGraph()

    def _init_agent(self):
        form_dims = 3 * 5
        link_dims = 5 * 3
        label_dims = self._input_labeler.get_num_labels()
        self.agent = agent.NAgent(n_state_dims=form_dims+link_dims+label_dims, n_actions=8)

    def navigate_to_url(self, url):
        self.d.get(url)

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
            if self._image_ssim(old_state_obj.screenshot, new_state_obj.screenshot) > old_state_obj.ssim_minimum:
                match = True
            if match == True:
                return(old_state_obj)
        return(None)

    def _construct_current_state(self):
        logging.debug('Constructing the current state as object')
        new_state_obj = DomState(
            dom=self.d.execute_script("return document.documentElement.outerHTML;"),
            text=self.d.find_element_by_tag_name('body').text,
            url=self.d.current_url,
            absolute=False if self.get_current_state() and self.d.current_url == self.get_current_state().url else True,
            screenshot=os.path.join("command_cache", uuid.uuid4().hex[:7] + ".png"),
            seed=self.seed,
        )
        logging.debug('Completed constructing the current state as object')
        elements = self.get_current_elements()
        for e in elements:
            e.dom_state = new_state_obj
        return(new_state_obj, elements)

    def _construct_state_vector(self, state):
        forms = collections.OrderedDict()
        links = collections.OrderedDict()
        labels = collections.OrderedDict()
        for e in state.elements:
            if e.tag == 'form':
                phrases = []
                for c in e.children:
                    if c.placeholder: phrases.append(c.placeholder)
                if phrases: forms[e] = self.agent.d2v(phrases)
            elif e.tag == 'a':
                if e.placeholder: links[e] = self.agent.w2v(e.placeholder)
        for label in self._input_labeler.get_labels():
            if self.session.query(DomElement).filter_by(label=label).filter(DomElement.value != None).first():
                labels[label] = 1.0
            else:
                labels[label] = 0.0
        state_vector = np.array([])
        elements = []
        for i in range(0, 3):
            try:
                form = forms.items()[i]
                state_vector = np.concatenate((state_vector, form[1]))
                elements.append(form[0])
            except IndexError:
                state_vector = np.concatenate((state_vector, np.zeros(5)))
                elements.append(None)
        for i in range(0, 5):
            try:
                link = links.items()[i]
                state_vector = np.concatenate((state_vector, link[1]))
                elements.append(link[0])
            except IndexError:
                state_vector = np.concatenate((state_vector, np.zeros(3)))
                elements.append(None)
        state_vector = np.concatenate((state_vector, labels.values()))
        return(state_vector, elements)

    def save_state(self):
        """
        At this point the current state points to previous state as browser just entered a new state
        Now we will save this if it is a previously undiscovered state.
        """
        logging.debug("Trying to save this state if this is previously undetected")
        new_state_obj, elements = self._construct_current_state()
        self.d.save_screenshot(new_state_obj.screenshot)
        state = self._check_if_duplicate_state(new_state_obj)
        if state == None:
            state = self._add_state(new_state_obj, elements)
            self.DG.add_node(state.id, url=state.url, absolute=state.absolute, seed=self.seed)
            self._current_state_id = state.id
            logging.debug("Adding new state as no existing matched (ID: %d Absolute: %s URL : %s)" % (state.id, state.absolute, state.url))
        else:
            self._current_state_id = state.id
            logging.debug("State already found as %d" % (state.id))

    def _add_state(self, new_state_obj, elements):
        self.session.add_all([new_state_obj] + elements)
        self.session.commit()
        return(new_state_obj)

    @staticmethod
    def _image_ssim(img1, img2):
        imageA = imread(img1, flatten=True)
        imageB = imread(img2, flatten=True)
        if imageA.shape == imageB.shape:
            return ssim(imageA, imageB)
        else:
            return(0.0)

    def quit(self):
        """
        A method to cleanly close everything
        """
        nx.write_graphml(self.DG, path=self.GRAPH_PATH)
        self.session.close()
        self.d.quit()
        if self.agent == False:
            self.agent.close()

    def get_current_elements(self):
        logging.debug('Getting current element objects')
        elements = []
        # strings = utilities.get_strings(self.d)
        # import pdb
        # pdb.set_trace()
        logging.debug('Iterating over elements to create objects')
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
                elements.append(DomElement(
                    tag='form',
                    xpath=utilities.get_element_xpath(f),
                ))
                for i in temp_form_inputs:
                    i.parent = elements[-1]
                elements += temp_form_inputs
                temp_form_inputs = []
        logging.debug('Elements gathered')
        return(elements)

    def _update_elements(self, e, state_id=None):
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
                self._update_elements(e)
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
                            self._update_elements(e)
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

    def ask_agent(self):
        print(self._construct_state_vector(self.get_current_state()))


    def fill_form(self, xpath='//*[@id="logon_form"]', attempt=0):
        if attempt < 3:
            elements = []
            values = {}
            form = None
            for i in self.get_current_state().elements:
                if i.xpath == xpath:
                    form = i
                    elements = i.children
                    break
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
                    e.value = payload
                    self.session.merge(e)  # Commit only when success
                time.sleep(1)
            if form:
                self.d.find_element_by_xpath(form.xpath).submit()
                if not self._form_fill_success(form):
                    self.navigate_to_state(self._current_state_id)
                    self.fill_form(xpath, attempt=attempt+1)
                else:
                    self.session.commit()
        else:
            logging.debu("Form fill failed multiple times and leaving it. Humse na ho payi!!")
            self.session.rollback()

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
        if old_input_count > 0.8 * len(form.children) or (new_lines_count > 0 and new_vector_count > 0.8 * new_lines_count):
            logging.debug("Form fill considered as fail")
            return(False)
        else:
            logging.debug("Form fill considered as success")
            return(True)


if __name__ == "__main__":
    try:
        b = None
        b = NBrowser()
        # b.navigate_to_url('file:///Users/tunnelshade/Downloads/YodleeLabs-Registration.htm')
        # b.navigate_to_url('https://moneycenter.yodlee.com/moneycenter/mfaregistration.moneycenter.do?_flowId=mfaregistration&c=csit_key%3AVZl14EfWF4rGSHQ1F6NEZWFU%2Bo8%3D&l=_flowId')
        # b.navigate_to_url('http://clin.cmcvellore.ac.in/onlineIPO/Patdetails/Home.aspx')
        b.navigate_to_url('https://signup.ballparkapp.com/')
        # b.navigate_to_url('https://hujplpiqmu.ballparkapp.com/session/new')
        # b.navigate_to_url('https://twitter.com/signup')
        b.save_state()
        b.enhance_state_info()
        b.ask_agent()
        # b.fill_form()
    except KeyboardInterrupt:
        pass
    except Exception, e:
        print(traceback.print_exc())
    finally:
        if b: b.quit()
