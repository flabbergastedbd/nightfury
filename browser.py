import os
import json
import uuid
import config
import difflib
import help2vec
import utilities
import numpy as np
import networkx as nx
import traceback
import labels
import logging

from skimage.measure import compare_ssim as ssim
from scipy.misc import imread
from selenium import webdriver
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy import Table, Column, Integer, String, Boolean,\
            Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property, hybrid_method
from selenium.common.exceptions import InvalidSelectorException, NoSuchElementException


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
    vector_string = Column(String)
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
    def vector(self):
        return(json.loads(self.vector_string) if self.vector_string else None)

    @hybrid_property
    def mandatory(self):
        if (self.placeholder and '*' in self.placeholder) or self.vector_string:
            return(True)
        else:
            return(False)


class NBrowser(object):
    DB_PATH = 'states.db'
    GRAPH_PATH = 'states.graphml'
    def __init__(self):
        self._init_selenium_driver()
        self._init_sqlalchemy_session()
        self._init_networkx_graph()

        self.seed = uuid.uuid4().hex[:5]
        self._current_state_id = 0
        self._input_labeler = labels.InputLabeler()

    def _init_selenium_driver(self):
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
        new_state_obj = DomState(
            dom=self.d.execute_script("return document.documentElement.outerHTML;"),
            text=self.d.find_element_by_tag_name('body').text,
            url=self.d.current_url,
            absolute=False if self.get_current_state() and self.d.current_url == self.get_current_state().url else True,
            screenshot=os.path.join("command_cache", uuid.uuid4().hex[:7] + ".png"),
            seed=self.seed,
        )
        elements = self.get_current_elements()
        for e in elements:
            e.dom_state = new_state_obj
        return(new_state_obj, elements)

    def save_state(self):
        """
        At this point the current state points to previous state as browser just entered a new state
        Now we will save this if it is a previously undiscovered state.
        """
        new_state_obj, elements = self._construct_current_state()
        self.d.save_screenshot(new_state_obj.screenshot)
        state = self._check_if_duplicate_state(new_state_obj)
        if state == None:
            state = self._add_state(new_state_obj, elements)
            self.DG.add_node(state.id, url=state.url, absolute=state.absolute, seed=self.seed)
            self._current_state_id = state.id
            logging.info("Adding new state as no existing matched (ID: %d Absolute: %s URL : %s)" % (state.id, state.absolute, state.url))
        else:
            self._current_state_id = state.id
            logging.info("State already found as %d" % (state.id))

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

    def get_current_elements(self):
        elements = []
        for f in self.d.find_elements_by_tag_name('form'):
            temp_form_inputs = []
            for i in f.find_elements_by_tag_name('input'):
                if i.is_displayed():
                    input_placeholder = utilities.get_placeholder(self.d, i)

                    input_maxlength = i.get_attribute('maxlength')
                    if input_maxlength: input_maxlength = int(input_maxlength)

                    input_type = i.get_attribute("type")
                    input_label = self._input_labeler.get_label(input_placeholder) if input_placeholder and input_type not in config.NON_TEXT_INPUT_TYPES else None
                    temp_form_inputs.append(DomElement(
                        tag="input",
                        placeholder=input_placeholder,
                        xpath=utilities.get_element_xpath(i),
                        help=None,
                        value=None,
                        maxlength=input_maxlength,
                        type=input_type,
                        name=i.get_attribute('name'),
                        location_x=i.location["x"],
                        location_y=i.location["y"],
                        size_w=i.size["width"],
                        size_h=i.size["height"],
                        label=input_label,
                    ))
            if len(temp_form_inputs) > 0:
                elements.append(DomElement(
                    tag='form',
                    xpath=utilities.get_element_xpath(f),
                ))
                for i in temp_form_inputs:
                    i.parent = elements[-1]
                elements += temp_form_inputs
                temp_form_inputs = []
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
        vec = help2vec.input_help_to_vec(lower_sen)
        enhanced = False
        if len(vec) > 0:  # Means it might be a help text. Now we have to link this with the corresponding input
            logging.info("[*] Following sentence was detected as input help")
            logging.info("[*] Sentence: %s" % (sen))
            logging.info("[*] Vector: %s" % (str(vec)))
            e = utilities.match_help_to_element_NLP(elements, lower_sen)
            if e and not e.help:  # We found reference to a placeholder so fine.
                logging.info("[*] Found following element for input help by placeholder reference")
                logging.info("[*] Element: %s" % (str(e)))
                e.help = sen
                e.vector_string = json.dumps(vec)
                self._update_elements(e)
                enhanced = True
            else: # We couldn't find reference to placeholder. So visual correlation
                try:  # Check if element still exists
                    elem = self.d.find_element_by_xpath("//*[contains(text(), '%s')]" % (sen))
                    if elem:
                        e = utilities.match_help_to_element_visually(elements, elem.location, elem.size)
                        if e and not e.help:  # We found reference to a placeholder so fine.
                            logging.info("[*] Found following element for input help by visual reference")
                            logging.info("[*] Element: %s" % (str(e)))
                            e.help = sen
                            e.vector_string = json.dumps(vec)
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
            logging.info("[*] Information will now be extracted from this state")
            for sen in self.get_current_state().text.splitlines():
                elements = self.get_current_state().elements
                self._enhance_element_info(sen, elements)
            current_state = self.get_current_state()
            current_state.nlp_analysis = True
            current_state = self._update_state(current_state)
        else:
            logging.info("[*] Information is already extracted from this state")

    def fill_form(self, xpath="//*[@id=\"registration_form\"]", attempt=0):
        if attempt < 3:
            elements = []
            form = None
            for i in self.get_current_state().elements:
                if i.xpath == xpath:
                    form = i
                    elements = i.children
                    break
            for e in elements:
                d_e = self.d.find_element_by_xpath(e.xpath)
                if e.type == "checkbox" and e.mandatory:
                    d_e.click()
                if e.type == "radio" and not d_e.is_selected():
                    try:
                        elem = self.d.find_element_by_css_selector("input[name='%s']:checked" % (e.name))
                        e.value = ''
                    except NoSuchElementException:
                        d_e.click()
                        e.value = d_e.get_attribute("value")
                else:
                    payload = utilities.get_input_value(e, elements)
                    sibling_e = self.session.query(DomElement).filter_by(label=e.label).filter(DomElement.value != None).first()
                    if not payload and sibling_e:
                        payload = sibling_e.value
                    d_e.send_keys(payload)
                    if not e.value and payload:
                        e.value = payload
                self._update_elements(e)
            if form:
                self.d.find_element_by_xpath(form.xpath).submit()
                if not self._form_fill_success(form):
                    self.navigate_to_state(self._current_state_id)
                    self.fill_form(xpath, attempt=attempt+1)
        else:
            raise

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
        if i > 0.8 * len(diff) and old_input_count > 0.8 * len(form.children):
            logging.info("[*] Form fill considered as fail")
            return(False)
        else:
            logging.info("[*] Form fill considered as success")
            return(True)


if __name__ == "__main__":
    try:
        logging.basicConfig(level=logging.INFO)
        b = None
        b = NBrowser()
        # b.navigate_to_url('file:///Users/tunnelshade/Downloads/YodleeLabs-Registration.htm')
        b.navigate_to_url('https://moneycenter.yodlee.com/moneycenter/mfaregistration.moneycenter.do?_flowId=mfaregistration&c=csit_key%3AVZl14EfWF4rGSHQ1F6NEZWFU%2Bo8%3D&l=_flowId')
        b.save_state()
        b.enhance_state_info()
        b.fill_form()
        # import time
        # time.sleep(20)
    except KeyboardInterrupt:
        pass
    except Exception, e:
        print(traceback.print_exc())
    finally:
        if b: b.quit()
