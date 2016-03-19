#!/usr/bin/env python
from rlpy.Agents import SARSA
from rlpy.Representations import IncrementalTabular, RBF
from rlpy.Policies import eGreedy
from rlpy.Experiments import Experiment
from selenium import webdriver
from xvfbwrapper import Xvfb
import numpy as np
import hack_domain
import os
import pickle
import signal
import traceback
import nf_shared

def agent_pickle(r, action=0):
    attrs = ['lambda_', 'eligibility_trace', 'eligibility_trace_s']
    for i in attrs:
        path = os.path.join('command_cache', i)
        if action == 0 and getattr(r, i, None) != None:  # Pickle
            print("Pickling %s" % (i))
            with open(path, 'wb') as f:
                pickle.dump(getattr(r, i), f)
        elif action == 1 and os.path.exists(path):  # Unpickle
            print("Unpickling %s" % (i))
            with open(path, 'rb') as f:
                setattr(r, i, pickle.load(f))
    return r

def representation_pickle(r, action=0):
    attrs = ['weight_vec', 'bins_per_dim', 'binWidth_per_dim', 'agg_states_num', 'random_state', 'hash', 'features_num']
    for i in attrs:
        path = os.path.join('command_cache', i)
        if action == 0:  # Pickle
            print("Pickling %s" % (i))
            with open(path, 'wb') as f:
                pickle.dump(getattr(r, i), f)
        elif action == 1 and os.path.exists(path):  # Unpickle
            print("Unpickling %s" % (i))
            with open(path, 'rb') as f:
                setattr(r, i, pickle.load(f))
    return r


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
    global representation
    representation = IncrementalTabular(domain, discretization=20)
    representation = representation_pickle(representation, action=1)
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
    global agent
    agent = SARSA(representation=representation, policy=policy,
                       discount_factor=domain.discount_factor,
                       initial_learn_rate=0.1,
                       learn_rate_decay_mode="boyan", boyan_N0=100,
                       lambda_=0.4)
    agent = agent_pickle(agent, action=1)
    opt["agent"] = agent
    opt["checks_per_policy"] = 10
    opt["max_steps"] = 5000
    opt["num_policy_checks"] = 10
    experiment = Experiment(**opt)
    return experiment

if __name__ == '__main__':
    try:
        nf_shared.browser = webdriver.PhantomJS()
        # nf_shared.browser = webdriver.Chrome()
        experiment = make_experiment(exp_id=1)
        experiment.run(visualize_steps=True,  # should each learning step be shown?
                       visualize_learning=True,  # show policy / value function?
                       visualize_performance=0)  # show performance runs?
        # experiment.plot()
        experiment.save()
    except KeyboardInterrupt:
        pass
    except Exception, e:
        print(traceback.format_exc())
    finally:
        nf_shared.browser.service.process.send_signal(signal.SIGTERM)
        nf_shared.browser.quit()
        agent_pickle(agent, action=0)
        representation_pickle(representation, action=0)

