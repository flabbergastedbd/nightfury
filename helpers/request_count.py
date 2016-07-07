import os
import re
import hashlib

DIR = '/tmp/request_cache'

if not os.path.exists(DIR):
    os.mkdir(DIR)


def response(context, flow):
    if not re.match("(?:js|css|jpeg|png)$", flow.request.path):
        hash_string = flow.request.path
        if flow.request.query:
            params = flow.request.query.keys()
            params.sort()
            hash_string = hash_string + '?' + '&'.join(params)
        open(os.path.join(DIR, hashlib.md5(hash_string).hexdigest()), 'w').close()
