from math import sqrt, log
from typing import Callable, Any

import scipy

from aalpy.learning_algs.stochastic_passive.helpers import Node

Score = bool | float
LocalScoreFunction = Callable[[Node, Node], Score]
GlobalScoreFunction = Callable[[dict[Node, Node]], Score]

class ScoreCalculation:
    def __init__(self, local_score : LocalScoreFunction = None, global_score : GlobalScoreFunction = None):
        # This is a hack that gives an simple implementation where we can easily
        # - determine whether the default is overridden (for optimization)
        # - override behavior in a functional way by providing the functions as arguments (no extra class)
        # - override behavior in a stateful way by implementing a new class
        if not hasattr(self, "local_score"):
            self.local_score = local_score or self.default_local_score
        if not hasattr(self, "global_score"):
            self.global_score = global_score or self.default_global_score

    def reset(self):
        pass

    @staticmethod
    def default_local_score(a, b):
        return True

    @staticmethod
    def default_global_score(part):
        return True

    def has_default_global_score(self):
        return self.global_score is self.default_global_score

    def has_default_local_score(self):
        return self.local_score is self.default_local_score

def hoeffding_compatibility(eps, compare_original = True) -> LocalScoreFunction:
    eps_fact = sqrt(0.5 * log(2 / eps))
    count_name = "original_count" if compare_original else "count"

    def similar(a: Node, b: Node):
        for in_sym in filter(lambda x : x in a.transitions.keys(), b.transitions.keys()):
            # could create appropriate dict here
            a_trans, b_trans = (x.transitions[in_sym] for x in [a,b])
            a_total, b_total = (sum(getattr(x, count_name) for x in trans.values()) for trans in (a_trans, b_trans))
            if a_total == 0 or b_total == 0:
                continue
            threshold = eps_fact * (sqrt(1 / a_total) + sqrt(1 / b_total))
            for out_sym in set(a_trans.keys()).union(b_trans.keys()):
                ac, bc = (getattr(x[out_sym], count_name) if out_sym in x else 0 for x in (a_trans, b_trans))
                if abs(ac / a_total - bc / b_total) > threshold:
                    return False
        return True
    return similar

def non_det_compatibility(eps) -> LocalScoreFunction:
    print("Warning: using experimental compatibility criterion for nondeterministic automata")
    def similar(a: Node, b: Node, _: Any):
        for in_sym in filter(lambda x : x in a.transitions.keys(), b.transitions.keys()):
            a_trans, b_trans = (x.transitions[in_sym] for x in [a,b])
            a_total, b_total = (sum(x.count for x in x.values()) for x in (a_trans, b_trans))
            if a_total < eps or b_total < eps:
                continue
            if set(a_trans.keys()) != set(b_trans.keys()):
                return False
        return True
    return similar

def local_to_global_score(local_fun : LocalScoreFunction) -> GlobalScoreFunction:
    def fun(part : dict[Node, Node]):
        for old_node, new_node in part.items():
            if local_fun(new_node, old_node) is False:
                return False
        return True
    return fun

def differential_info(part : dict[Node, Node]):
    relevant_nodes_old = list(part.keys())
    relevant_nodes_new = set(part.values())

    partial_llh_old = sum(node.local_log_likelihood_contribution() for node in relevant_nodes_old)
    partial_llh_new = sum(node.local_log_likelihood_contribution() for node in relevant_nodes_new)

    num_params_old = sum(1 for node in relevant_nodes_old for _ in node.transition_iterator())
    num_params_new = sum(1 for node in relevant_nodes_new for _ in node.transition_iterator())

    return partial_llh_old - partial_llh_new, num_params_old - num_params_new

def lower_threshold(value, thresh):
    if isinstance(value, Callable): # can be used to wrap score functions
        def fun(*args, **kwargs):
            return lower_threshold(value(*args, **kwargs), thresh)
        return fun
    return value if thresh < value else False

def likelihood_ratio_global_score(alpha : float) -> GlobalScoreFunction:
    def score_fun(part : dict[Node, Node]) :
        llh_diff, param_diff = differential_info(part)
        score = scipy.stats.chi2.pdf(2*(llh_diff), param_diff)
        return lower_threshold(score, alpha) # Not entirely sure if implemented correctly
    return score_fun

def AIC_global_score(alpha : float = 0) -> GlobalScoreFunction:
    def score(part : dict[Node, Node]) :
        llh_diff, param_diff = differential_info(part)
        return lower_threshold(param_diff - llh_diff, alpha)
    return score

def EDSM_global_score(min_evidence = -1) -> GlobalScoreFunction:
    def score(part : dict[Node, Node]):
        total_evidence = 0
        for old_node, new_node in part.items():
            for in_sym, trans_old in old_node.transitions.items():
                trans_new = new_node.transitions.get(in_sym)
                if not trans_new:
                    continue
                for out_sym, trans_info in trans_old.items():
                    if out_sym in trans_new:
                        total_evidence += trans_info.count
        return lower_threshold(total_evidence, min_evidence)
    return score