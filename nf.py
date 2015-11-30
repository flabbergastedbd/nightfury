import os
import re
import sys
import json
import numpy as np
import random
import subprocess

from scipy import array
from pybrain.rl.learners.valuebased import ActionValueNetwork
from pybrain.rl.agents import LearningAgent
from pybrain.rl.learners import SARSA, NFQ
from pybrain.rl.experiments import EpisodicExperiment
from pybrain.rl.explorers import EpsilonGreedyExplorer, DiscreteStateDependentExplorer
from pybrain.rl.environments.episodic import EpisodicTask
from pybrain.rl.environments.environment import Environment

class HackTask(EpisodicTask):
    def isFinished(self):
        finished = False
        if self.env.getSensorByName('version') != 0:
            finished = True
        return(finished)

    def getReward(self):
        reward = 0
        if self.env.getSensorByName('version') != 0:
            reward = 5
        else:
            if self.env._backup_status["cms"] != self.env.status["cms"]:
                reward = 3
            else:
                reward = -5
        print("Reward: %d" % (reward))
        return reward

    def getObservation(self):
        return(self.env.getSensors())

class HackEnvironment(Environment):
    indim = 5
    outdim = 2

    def __init__(self, url):
        self.url = url
        self.reset()
        self.actions = [
            "run_whatweb",
            "run_wpscan",
            "run_joomscan",
            "run_droopscan"]

    def reset(self):
        self.status = {"cms": 0, "version": 0}

    def getSensors(self):
        return(self.status.values())

    def getSensorByName(self, name):
        return(self.status.get(name, None))

    def performAction(self, action):
        self._backup_status = dict(self.status)
        print(action)
        print(self.actions[int([action][0])])
        getattr(self, self.actions[int([action][0])])()

    def run_whatweb(self):
        if self.url == 'http://typographica.org':
            self.status["cms"] = 1
        elif self.url == 'https://www.drupal.org':
            self.status["cms"] = 2
        elif self.url == 'http://www.mb-photography.com':
            self.status["cms"] = 3
        return
        f = os.path.join("/tmp", str(random.randint(1000, 9999)))
        p = subprocess.Popen(["whatweb", "-q", "--log-json", str(f), self.url])
        r = p.wait()
        data = json.load(open(f, 'r'))
        if "WordPress" in data["plugins"]:
            self.status["cms"] = 1
        elif "Drupal" in data["plugins"]:
            self.status["cms"] = 2
        elif "Joomla" in data["plugins"]:
            self.status["cms"] = 3
        os.remove(f)

    def run_joomscan(self):
        if self.url == 'http://www.mb-photography.com':
            print("Joomla version identified")
            self.status['version'] = 1
        return
        data = subprocess.check_output(["joomscan", "-pe", "-nf", "-u", self.url])
        if re.search("Is it sure a Joomla\?", data):
            return
        self.status["version"] = 1
        print("Joomla version identified")

    def run_droopscan(self):
        if self.url == 'https://www.drupal.org':
            print("Drupal version identified")
            self.status['version'] = 1
        return
        data = subprocess.check_output(["droopescan", "scan", "drupal", "-e", "v", "-u", self.url])
        if re.search("No version found", data):
            return
        self.status["version"] = 1
        print("Drupal version identified")

    def run_wpscan(self):
        if self.url == 'http://typographica.org':
            print("Wordpress version identified")
            self.status['version'] = 1
        return
        try:
            data = subprocess.check_output(["wpscan", "--no-color", "--url", self.url])
        except subprocess.CalledProcessError, e:
            data = e.output
        if re.search("WordPress version can not be detected", data):
            return
        self.status["version"] = 1
        print("Wordpress version identified")


controller = ActionValueNetwork(2, 4)

learner = NFQ()
learner._setExplorer(EpsilonGreedyExplorer(epsilon=0.3))
agent = LearningAgent(controller, learner)
batch = 10

for u in ['http://typographica.org', 'https://www.drupal.org', 'http://www.mb-photography.com']:
    for i in range(0, batch):
        environment = HackEnvironment(u)
        task = HackTask(environment)
        experiment = EpisodicExperiment(task, agent)

        experiment.doEpisodes(5)
        agent.learn(5)
        print("Batch done")

for s in [0, 1, 2, 3]:
    agent.newEpisode()
    environment.reset()
    environment.status['cms'] = s
    print(agent.getAction())
