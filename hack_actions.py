import numpy as np

class HackAction(object):
    dependent_dims = []
    dependency_dims = []

    def __str__(self):
        return(str_repr)

    def __unicode__(self):
        return(str_repr)


class Whatweb(HackAction):

    def run(self, url):
        cms = 0
        if url == 'http://typographica.org':
            cms = 'WordPress'
        elif url == 'https://www.drupal.org':
            cms = 'Drupal'
        elif url == 'http://www.mb-photography.com':
            cms = 'Joomla'
        return({'cms': cms})
        f = os.path.join("/tmp", str(random.randint(1000, 9999)))
        p = subprocess.Popen(["whatweb", "-q", "--log-json", str(f), url])
        r = p.wait()
        data = json.load(open(f, 'r'))
        if "WordPress" in data["plugins"]:
            cms = 'WordPress'
        elif "Drupal" in data["plugins"]:
            cms = 'Drupal'
        elif "Joomla" in data["plugins"]:
            cms = 'Joomla'
        os.remove(f)
        return({'cms': cms})


class Wpscan(HackAction):
    dependent_dims = ['cms']

    def run(self, url):
        version = 0
        if url == 'http://typographica.org':
            # print("Wordpress version identified")
            version = 'Detected'
        return({'cms_version': version})
        try:
            data = subprocess.check_output(["wpscan", "--no-color", "--url", url])
        except subprocess.CalledProcessError, e:
            data = e.output
        version = 0 if re.search("WordPress version can not be detected", data) else 'Detected'
        return({'cms_version': version})

class Joomscan(HackAction):
    dependent_dims = ['cms']

    def run(self, url):
        version = 0
        if url == 'http://www.mb-photography.com':
            # print("Joomla version identified")
            version = 'Detected'
        return({'cms_version': version})
        data = subprocess.check_output(["joomscan", "-pe", "-nf", "-u", url])
        version = 0 if re.search("Is it sure a Joomla\?", data) else 'Detected'
        return({'cms_version': version})


class Droopescan(HackAction):
    dependent_dims = ['cms']

    def run(self, url):
        version = 0
        if url == 'https://www.drupal.org':
            # print("Drupal version identified")
            version = 'Detected'
        return({'cms_version': version})
        data = subprocess.check_output(["droopescan", "scan", "drupal", "-e", "v", "-u", url])
        version = 0 if re.search("No version found", data) else 'Detected'
        return({'cms_version': version})
