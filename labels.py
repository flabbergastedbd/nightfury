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
            self.labels_json = json.load(fp)

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
        if text not in [i["text"] for i in self.labels_json]:
            self.labels_json.append({"text": text, "label": "unknown"})
            with open(self.LABELS_DATA, 'w') as fp:
                json.dump(self.labels_json, fp, indent=4)

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
    return(None)

if __name__ == "__main__":
    i_labeler = InputLabeler()
    for i in ["address", "zip/pin code", "mobile number", "email", "Terms and Conditions"]:
        print("%s: %s" % (i, i_labeler.get_label(i)))
