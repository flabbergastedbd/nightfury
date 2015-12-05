import os
import re
import md5
import json
import subprocess
import numpy as np

class HackAction(object):
    dependent_dims = []
    dependency_dims = []

    def hash_string(self, s):
        m = md5.new()
        m.update(s)
        return(m.hexdigest())

    def run_command(self, c_list, f=None):
        """
        If f is provided then the file content is cached and returned everytime
        """
        content = ''
        if not os.path.exists('command_cache'):
            os.makedirs('command_cache')
        path = os.path.join('command_cache', self.hash_string(' '.join(c_list)))
        if os.path.exists(path):
            content = open(path, 'r').read()
        else:
            try:
                print("Running %s" % (' '.join(c_list)))
                content = subprocess.check_output(c_list)
            except subprocess.CalledProcessError, e:
                print("Command %s exited with non-zero status" % (' '.join(c_list)))
                content = e.output
            if f != None:
                content = open(f, 'r').read()
                os.remove(f)
            with open(path, 'w') as fp:
                fp.write(content)
        return(content)

    def __str__(self):
        return(str_repr)

    def __unicode__(self):
        return(str_repr)


class Whatweb(HackAction):

    def run(self, url):
        cms = 0
        f = os.path.join("/tmp", self.hash_string(url))
        data = self.run_command(["whatweb", "-q", "--log-json", str(f), url], f=f)
        data = json.loads(data)
        if "WordPress" in data["plugins"]:
            cms = 'WordPress'
        elif "Drupal" in data["plugins"]:
            cms = 'Drupal'
        elif "Joomla" in data["plugins"]:
            cms = 'Joomla'
        return({'cms': cms})


class Wpscan(HackAction):
    dependent_dims = ['cms']

    def run(self, url):
        version = 0
        data = self.run_command(["wpscan", "--no-color", "--batch", "--url", url])
        version = 0 if re.search("WordPress version can not be detected", data) else 'Detected'
        return({'cms_version': version})

class Joomscan(HackAction):
    dependent_dims = ['cms']

    def run(self, url):
        version = 0
        data = self.run_command(["joomscan", "-pe", "-nf", "-u", url])
        version = 0 if re.search("Is it sure a Joomla\?", data) else 'Detected'
        return({'cms_version': version})


class Droopescan(HackAction):
    dependent_dims = ['cms']

    def run(self, url):
        version = 0
        data = self.run_command(["droopescan", "scan", "drupal", "-e", "v", "-u", url])
        version = 0 if re.search("No version found", data) else 'Detected'
        return({'cms_version': version})
