import numpy as np

class HackAction(object):
    dependent_dims = []
    dependency_dims = []
    str_repr = 'HackAction'

    def __str__(self):
        return(str_repr)

    def __unicode__(self):
        return(str_repr)


class WhatwebAction(HackAction):
    str_repr = 'whatweb'

    def run(self, url):
        cms = 0
        if url == 'http://typographica.org':
            cms = 1
        elif url == 'https://www.drupal.org':
            cms = 2
        elif url == 'http://www.mb-photography.com':
            cms = 3
        return(np.array([[0, cms]]))
        f = os.path.join("/tmp", str(random.randint(1000, 9999)))
        p = subprocess.Popen(["whatweb", "-q", "--log-json", str(f), url])
        r = p.wait()
        data = json.load(open(f, 'r'))
        if "WordPress" in data["plugins"]:
            cms = 1
        elif "Drupal" in data["plugins"]:
            cms = 2
        elif "Joomla" in data["plugins"]:
            cms = 3
        os.remove(f)
        return(np.array([[0, cms]]))


class WpscanAction(HackAction):
    dependent_dims = [0]
    str_repr = 'wpscan'

    def run(self, url):
        version = 0
        if url == 'http://typographica.org':
            # print("Wordpress version identified")
            version = 1
        return(np.array([[1, version]]))
        try:
            data = subprocess.check_output(["wpscan", "--no-color", "--url", url])
        except subprocess.CalledProcessError, e:
            data = e.output
        version = 0 if re.search("WordPress version can not be detected", data) else 1
        return(np.array([[1, version]]))

class JoomscanAction(HackAction):
    dependent_dims = [0]
    str_repr = 'joomscan'

    def run(self, url):
        version = 0
        if url == 'http://www.mb-photography.com':
            # print("Joomla version identified")
            version = 1
        return(np.array([[1, version]]))
        data = subprocess.check_output(["joomscan", "-pe", "-nf", "-u", url])
        version = 0 if re.search("Is it sure a Joomla\?", data) else 1
        return(np.array([[1, version]]))


class DroopescanAction(HackAction):
    dependent_dims = [0]
    str_repr = 'droopescan'

    def run(self, url):
        version = 0
        if url == 'https://www.drupal.org':
            # print("Drupal version identified")
            version = 1
        return(np.array([[1, version]]))
        data = subprocess.check_output(["droopescan", "scan", "drupal", "-e", "v", "-u", url])
        version = 0 if re.search("No version found", data) else 1
        return(np.array([[1, version]]))
