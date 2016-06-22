import os
import json
import hashlib
import filelock

import tornado.web
import tornado.ioloop
import tornado.template
import tornado.httpserver
import tornado.options

PLACEHOLDER_DIR = './placeholders'

for i in [PLACEHOLDER_DIR]:
    if not os.path.exists(i):
        os.makedirs(i)

class PlaceholderDataHandler(tornado.web.RequestHandler):
    def post(self):
        data = json.loads(self.request.body)
        for form in data:
            form_string = json.dumps(form)
            filename = os.path.join(PLACEHOLDER_DIR, hashlib.sha1(form_string).hexdigest() + '.json')
            lock = filelock.FileLock(filename)
            with lock:
                with open(filename, 'w') as f:
                    f.write(form_string)

def make_app():
    return tornado.web.Application([
        (r"/placeholders", PlaceholderDataHandler),
    ])

if __name__ == "__main__":
    try:
        server = tornado.httpserver.HTTPServer(make_app())
        server.bind(80, address='0.0.0.0')
        tornado.options.parse_command_line(
            args=["dummy_arg", "--log_file_prefix=./recorder.log", "--logging=info"])
        server.start(2)
        tornado.ioloop.IOLoop.instance().start()
    except KeyboardInterrupt:
        server.stop()
        tornado.ioloop.IOLoop.instance().stop()
