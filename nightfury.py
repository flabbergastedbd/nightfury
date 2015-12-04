#!/usr/bin/env python
from rlpy.Agents import SARSA
from rlpy.Representations import IncrementalTabular, RBF
from rlpy.Policies import eGreedy
from rlpy.Experiments import Experiment
import numpy as np
import hack_domain
import os


def make_experiment(exp_id=1, path="./results/ITab"):
    """
    Each file specifying an experimental setup should contain a
    make_experiment function which returns an instance of the Experiment
    class with everything set up.

    @param id: number used to seed the random number generators
    @param path: output directory where logs and results are stored
    """
    opt = {}
    opt["exp_id"] = exp_id
    opt["path"] = path

    # Domain:
    domain = hack_domain.HackDomain()
    opt["domain"] = domain

    # Representation
    representation = IncrementalTabular(domain, discretization=20)
    opt["path"] = "./results/ITab"
    """
    representation = RBF(domain, num_rbfs=int(206.),
                         resolution_max=25., resolution_min=25.,
                         const_feature=False, normalize=True, seed=exp_id)
    opt["path"] = "./results/RBF"
    """

    # Policy
    policy = eGreedy(representation, epsilon=0.2)

    # Agent
    opt["agent"] = SARSA(representation=representation, policy=policy,
                       discount_factor=domain.discount_factor,
                       initial_learn_rate=0.1,
                       learn_rate_decay_mode="boyan", boyan_N0=100,
                       lambda_=0.)
    opt["checks_per_policy"] = 100
    opt["max_steps"] = 20
    opt["num_policy_checks"] = 10
    experiment = Experiment(**opt)
    return experiment

if __name__ == '__main__':
    experiment = make_experiment(exp_id=1)
    experiment.run(visualize_steps=True,  # should each learning step be shown?
                   visualize_learning=True,  # show policy / value function?
                   visualize_performance=0)  # show performance runs?
    # experiment.plot()
    experiment.save()
