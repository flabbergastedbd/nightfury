import os
import sys
import json
import logging

from ..agent import NAgent
from ..utilities import clean_placeholder

if __name__ == "__main__":
    PLACEHOLDER_DIR = sys.argv[1]
    logging.basicConfig(format='%(asctime)s : %(levelname)s : %(message)s', level=logging.INFO)
    agent = NAgent(load_network=False)
    for (dirpath, dirnames, filenames) in os.walk(PLACEHOLDER_DIR):
        for filename in filenames:
            with open(os.path.join(PLACEHOLDER_DIR, filename), 'r') as f:
                data = json.loads(f.read())
            if data:
                placeholders = []
                for e in data:
                    try:
                        placeholder = clean_placeholder(e['placeholder']).encode('utf-8')
                        if placeholder:
                            placeholders.append(unicode(placeholder))
                    except TypeError:
                        print("Dumb error again")
                    except KeyError:
                        print("No placeholder")
                if placeholders:
                    vector = agent.d2v(placeholders)
                    print("%s --> %s" % (str(placeholders), str(vector)))
    agent.close()
