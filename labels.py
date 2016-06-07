import json
import config

from textblob import TextBlob
from textblob.classifiers import NaiveBayesClassifier

class InputLabeler(object):
    LABELS_DATA = 'labels_data.json'
    def __init__(self):
        with open(self.LABELS_DATA, 'r') as fp:
            self.c = NaiveBayesClassifier(fp, format="json")
        with open(self.LABELS_DATA, 'r') as fp:
            self.labels_json = {}
            for i in json.load(fp):
                self.labels_json[i['text']] = i['label']

    def get_num_labels(self):
        return(len(self.get_labels()))

    def get_labels(self):
        labels = self.labels_json.values()
        labels.sort()
        return(set(labels))

    def get_label(self, text):
        text = text.lower()
        # self.save_placeholder(text)
        prob_dist = self.c.prob_classify(text)
        label = prob_dist.max()
        prob = round(prob_dist.prob(label), 2)
        if prob > 0.7:
            return(label)
        else:
            return(None)

    def save_placeholder(self, text):
        try:
            self.labels_json[text]
        except KeyError:
            self.labels_json[text] = 'unknown'

        with open(self.LABELS_DATA, 'w') as fp:
            json.dump([{'text': k, 'label': v} for k,v in self.labels_json.items()], fp, indent=4)

def get_payload_for_label(label):
    if label == 'email':
        return(config.EMAIL_INPUT)
    elif label == 'mobile':
        return(config.MOBILE_INPUT)
    elif label == 'zipcode':
        return(config.ZIPCODE_INPUT)
    elif label == 'address':
        return(config.ADDRESS_INPUT)
    elif label == 'text':
        return(config.TEXT_INPUT)
    elif label == 'date':
        return(config.DATE_INPUT)
    elif label == 'password':
        return(config.PASSWORD_INPUT)
    return(None)

class HelpLabeler(object):
    HELP_DATA = 'help_data.json'
    def __init__(self):
        with open(self.HELP_DATA, 'r') as fp:
            self.c = NaiveBayesClassifier(fp, format="json")
        with open(self.HELP_DATA, 'r') as fp:
            self.help_json = {}
            for i in json.load(fp):
                self.help_json[i['text']] = i['label']

    def get_label(self, text, lower_placeholders=[]):
        text = text.lower()
        self.save_help(text)
        prob_dist = self.c.prob_classify(text)
        label = prob_dist.max()
        prob = round(prob_dist.prob(label), 2)
        if prob > 0.7:
            return(label)
        else:
            return(None)

    def save_help(self, lower_text):
        try:
            self.help_json[lower_text]
        except KeyError:
            self.help_json[lower_text] = 'unknown'

        with open(self.HELP_DATA, 'w') as fp:
            json.dump([{'text': k, 'label': v} for k, v in self.help_json.items()], fp, indent=4)


if __name__ == "__main__":
    i_labeler = InputLabeler()
    for i in ["re-enter password"]:
        print("%s: %s" % (i, i_labeler.get_label(i)))
