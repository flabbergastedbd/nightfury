import copy
import nltk
import random
import string
import text2num
import utilities

from pattern.en import parsetree, pprint, singularize, wordnet

def custom_similarity(word, synsets, pos=None):
    word = singularize(word.lower())
    similarities = []
    if pos:
        word_synsets = wordnet.synsets(word, pos=pos)
    else:
        word_synsets = wordnet.synsets(word)
    for i in synsets:
        for j in word_synsets:
            try:
                similarities.append(wordnet.similarity(i, j))
            except Exception, e:
                pass
                # print(e)
    return(max(similarities) if len(similarities) > 0 else 0)


def alphabet_similarity(word):
    return(custom_similarity(word, [wordnet.synsets('alphabet')[0], wordnet.synsets('character')[-2], wordnet.synsets('letter')[1]], pos=wordnet.NOUN))

def capital_similarity(word):
    return(custom_similarity(word, [wordnet.synsets('capital')[3]], pos=wordnet.NOUN))

def number_similarity(word):
    return(custom_similarity(word, [wordnet.synsets('number')[0], wordnet.synsets('number')[1], wordnet.synsets('number')[4]], pos=wordnet.NOUN))

def lowercase_similarity(word):
    return(custom_similarity(word, [wordnet.synsets('lowercase')[0], wordnet.synsets('lower')[0]]))

def uppercase_similarity(word):
    return(custom_similarity(word, [wordnet.synsets('uppercase')[0], wordnet.synsets('upper')[0]]))

def special_similarity(word):
    if word.startswith("special"):
        return(1.0)
    return(custom_similarity(word, [wordnet.synsets('special', pos=wordnet.ADJECTIVE)[1], wordnet.synsets('special', pos=wordnet.ADJECTIVE)[3]]))

def mandatory_similarity(word):
    return(custom_similarity(word, [wordnet.synsets('mandatory', pos=wordnet.ADJECTIVE)[0]]))


def operate(old_chars, new_chars, op):
    if op.get() == 0:
        old_chars.append(random.choice(new_chars))
    return(old_chars)

class Operator(object):
    OPS = [0, 1]
    def __init__(self, v=0):
        self.op = v

    def get(self):
        t = self.op
        self.op = 0
        return(t)

    def set(self, v):
        self.op = v


INPUT_VECTOR = {"length": 0, "chars": []}

def input_help_to_vec(p):
    t = parsetree(p)
    requirements = []
    mandatory = False
    # pprint(t)
    for sen in t:
        for i, chunk in enumerate(sen.chunks):
            if chunk.type == "ADJP":
                vector = copy.deepcopy(INPUT_VECTOR)
                for w in chunk.words:
                    if w.type.startswith("JJ") and mandatory_similarity(w.string) > 0.9:
                        mandatory = True
            if chunk.type == "NP":
                vector = copy.deepcopy(INPUT_VECTOR)
                adjv_nn_bridge = []
                op = Operator()  # 0 = and & 1 = or
                ignore = False  # Useful when have DT like no etc..
                for w in chunk.words:
                    if w.type == "CD":
                        try:
                            op.get()
                            vector["length"] = int(w.string)
                        except ValueError:
                            try:
                                vector["length"] = text2num.text2num(w.string)
                            except text2num.NumberException:
                                pass
                    elif w.type == "CC":
                        ignore = False
                        if w.string.lower() == "and":
                            op.set(0)
                        elif w.string.lower() == "or":
                            op.set(1)
                    elif w.type.startswith("NN"):
                        similarities = [alphabet_similarity(w.string), capital_similarity(w.string), number_similarity(w.string)]
                        m = max(similarities)
                        m_index = similarities.index(m)
                        if m > 0.9 and not ignore:
                            if m_index == 0:
                                if len(adjv_nn_bridge) == 0: adjv_nn_bridge.append(random.choice(list(string.lowercase)))
                                vector["chars"] = operate(vector["chars"], adjv_nn_bridge, op)
                            elif m_index == 1:
                                vector["chars"] = operate(vector["chars"], [random.choice(list(string.uppercase))], op)
                            elif m_index == 2:
                                vector["chars"] = operate(vector["chars"], [random.choice([str(i) for i in range(0, 10)])], op)
                    elif w.type.startswith("JJ"):
                        similarities = [lowercase_similarity(w.string), uppercase_similarity(w.string), special_similarity(w.string)]
                        m = max(similarities)
                        m_index = similarities.index(m)
                        if m > 0.9 and not ignore:
                            if m_index == 0:
                                adjv_nn_bridge = operate(adjv_nn_bridge, [random.choice(list(string.lowercase))], op)
                            elif m_index == 1:
                                adjv_nn_bridge = operate(adjv_nn_bridge, [random.choice(list(string.uppercase))], op)
                            elif m_index == 2:
                                adjv_nn_bridge = operate(adjv_nn_bridge, [random.choice(['!', '$'])], op)
                                if vector["length"] == 0: vector["length"] = 1
                        else:
                            op.get()  # If there is a CC it gets cleaned because we couldn't identify the adjective
                    elif w.type.startswith("DT"):
                        if w.string.lower().startswith("no"):
                            ignore = True

                requirements.append(vector)


    if mandatory and len(requirements) == 0: requirements.append({"length": 1, "chars": ['x']})
    # Handling conjunctions at sentence level
    # Merging vectors based on 'and' and 'or' as of now
    l = []
    last_chunk = None
    for w in t.words:
        if w.chunk == None and w.type.startswith("CC"):
            if w.string.lower() == "or":
                l.append(1)
        elif w.chunk and w.chunk.type == "NP":
            if last_chunk == None or (last_chunk != w.chunk):
                l.append(requirements.pop(0))
                last_chunk = w.chunk

    final = []
    i = 0
    while i < len(l):
        if l[i] == 1:
            i += 2
        else:
            if l[i]["length"] != 0 and len(l[i]["chars"]) > 0: final.append(l[i])
            i += 1
    return(final)

def input_vec_to_string(vectors):
    payload = ''
    if len(vectors) == 1 and vectors[0]["length"] > 0:
        payload = ''.join(vectors[0]["chars"]) * (vectors[0]["length"]/len(vectors[0]["chars"]))
    else:
        length = 0
        payload = ''
        for i, v in enumerate(vectors):
            if v["length"] > 1 and length == 0 and i == 0:
                length = v["length"]
            else:
                payload += ''.join(v["chars"]) * (v["length"]/len(v["chars"]))
        if length and len(payload) < length:
            payload += ''.join([random.choice(list(string.lowercase)) for i in range(0, length - len(payload))])
    return(''.join([utilities.get_alternate_char(c) for c in payload]))

def form_help_to_vec(p):
    t = parsetree(p)
    requirements = []
    # pprint(t)
    for sen in t:
        for i, chunk in enumerate(sen.chunks):
            if chunk.type == "NP":
                requirements.append(vector)
    return(final)

if __name__ == "__main__":
    texts = [
        "Must have at least 6 characters (with letters and numbers) and no special characters.",
        "Your password must be at least 8 characters long and contain at least one upper case letter, one number and any of these special characters !@#$%^&*()",
        "Use at least one lowercase letter, one numeral, and seven characters",
        "6 or more characters",
        "5 or 7 numbers",
        "5 numbers or 7 capitals",
        "5 numbers and 7 capitals",
        "Cannot contain special characters",
        "max 20 characters. no special characters"
    ]
    for p in texts:
        print(help2vec(p))
        print("\n")
