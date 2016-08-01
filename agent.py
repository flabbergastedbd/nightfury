import os
import d2v
import json
import math
import shutil
import numpy as np
import logging
import browser
import cPickle as pickle

from rlpy.Representations import RBF
from rlpy.Policies import eGreedy
from rlpy.Experiments import Experiment
from rlpy.Agents import LSPI_SARSA, SARSA


class Nightfury(object):
    def __init__(self):
        self._init_logging()
        self.d2v = d2v.D2V()

        self.browser = browser.NBrowser(self.d2v)

    def _init_logging(self):
        logger = logging.getLogger()
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)8s] --- %(message)s (%(filename)s:%(lineno)s)",
            "%H:%M")
        logger.setLevel(logging.DEBUG)

        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        handler.setLevel(logging.INFO)
        logger.addHandler(handler)

        file_handler = logging.FileHandler('/tmp/nightfury.log')
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.DEBUG)
        logger.addHandler(file_handler)

    def make_experiment(self, exp_id=1, path="results/"):
        opt = {}
        opt["exp_id"] = exp_id
        opt["path"] = path

        domain = self.browser
        opt["domain"] = domain

        representation = RBF(opt["domain"], num_rbfs=int(206,))
        policy = eGreedy(representation, epsilon=0.3)

        agent = SARSA(
            representation=representation,
            policy=policy,
            discount_factor=domain.discount_factor,
            initial_learn_rate=0.1,
            learn_rate_decay_mode="boyan",
            boyan_N0=100,
            lambda_=0.4
        )
        opt["agent"] = agent

        opt["checks_per_policy"] = 10
        opt["max_steps"] = 5000
        opt["num_policy_checks"] = 10
        experiment = Experiment(**opt)
        return(experiment)

    def run(self):
        exp = self.make_experiment()
        exp.run(visualize_steps=False)

    def close(self):
        if self.d2v: self.d2v.close()
        if self.browser: self.browser.close()


if __name__ == "__main__":
    # agent = NAgent()
    # print(agent.w2v('profile'))
    try:
        nf = None
        nf = Nightfury()
        nf.run()
    except KeyboardInterrupt:
        nf.close()
