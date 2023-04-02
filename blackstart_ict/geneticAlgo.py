import pymoo
import networkx as nx
import numpy as np
from pymoo.algorithms.moo.nsga2 import NSGA2

from pymoo.core.problem import Problem

from pymoo.operators.crossover.expx import ExponentialCrossover
from pymoo.operators.mutation.bitflip import BitflipMutation
from pymoo.operators.sampling.rnd import BinaryRandomSampling
from pymoo.optimize import minimize

G = nx.Graph()

def runner(amount_of_nodes, current_ict_graph):
    G = current_ict_graph
    problem = ProblemWrapper(n_var=amount_of_nodes, n_obj=2, xl=0, xu=1)
    method = NSGA2(pop_size=400,
                   sampling=BinaryRandomSampling(),
                   crossover=ExponentialCrossover(),
                   mutation=BitflipMutation(),
                   eliminate_duplicates=True,
                   )
    stop_criteria = ('n_gen', 5)

    result = minimize(
        problem=problem,
        algorithm=method,
        termination=stop_criteria,
        save_history=True,
        verbose=True
    )
    return result


class ProblemWrapper(Problem):

    def _evaluate(self, designs, out, *args, **kwargs):
        res = []

        for design in designs:
            res.append(solve(design))

        out['F'] = np.array(res)


def showGraphByDesign(graph=G, des=[]):
    nodes = graph.nodes
    node_list = list(nodes.keys())
    node_list_current = []
    counter = 0
    # if current entry in design is 1, then edge is part of the current tree, if it is 0 the edge is not part of the tree
    for key_list_entry in node_list:
        if des[counter] == 1:
            node_list_current.append(key_list_entry)
        counter += 1
    G_current = graph.subgraph(node_list_current).copy()
    return G_current
    
def sum_of_node_weights():
    counter = 0
    for node in list(G.nodes):
        counter += G.nodes[node]['ps_in_cov']
    return counter
    
def pathstuff_countpathstermialnodepairs(G_current):
    current_nodes_in_graph = list(G_current.nodes)
    current_nodes = []
    path_counter = 0
    abc = 0
    for node in current_nodes_in_graph:
        if G_current.nodes[node]['ps_in_cov'] >= 1:
            current_nodes.append(node)
    started_from_already = []
    for node in current_nodes:
        if node not in started_from_already:
            started_from_already.append(node)
            need_a_path_to = list(set(current_nodes) - set(started_from_already))
            for dest in need_a_path_to:
                # abc += len(list(nx.all_simple_paths(G_current, node, dest)))
                for path_discovered in nx.all_simple_paths(G_current, node, dest):
                    path_counter += 1
            # for path_discovered in nx.all_simple_paths(G_current, node, need_a_path_to):
            #     path_counter += 1
    return path_counter

       
def solve(design):
    steiner_nodes = []
    # print("in solve")
    for node in G.nodes:
        if G.nodes[node]['ps_in_cov'] > 1:
            steiner_nodes.append(node)
    G_current = showGraphByDesign(G, design)
    if not nx.is_empty(G_current):
        # if True:
        if all(node in G_current.nodes for node in steiner_nodes):
            if nx.is_connected(G_current):
                if netflow_tester.check_flow_constraint(G_current):
                    sumoftheweights_max_node = sum_of_node_weights()
                    sumoftheweights_min_node = 0
                    sumofpathes_max = pathstuff_countpathstermialnodepairs(G)
                    sumofpathes_min = 0
                    # node_weight calculation
                    nodeweight_current = 0
                    for node in G_current.nodes:
                        nodeweight_current += G_current.nodes[node]['ps_in_cov']
                    factor1 = 1 - (nodeweight_current - sumoftheweights_min_node) / (
                            sumoftheweights_max_node - sumoftheweights_min_node)

                    # number of paths between terminal nodes
                    number_of_paths = pathstuff_countpathstermialnodepairs(G_current)
                    # TODO is minimazation correct here??
                    factor2 = 1- (number_of_paths - sumofpathes_min) / (
                            sumofpathes_max - sumofpathes_min)
                    return (factor1, factor1)
                else:
                    # flow constraint is violated
                    return (804, 804)
            else:
                # Graph is not connected
                return (801, 801)
        else:
            # Not all terminal nodes are part of the graph
            return (802, 802)
    else:
        # the graph is empty
        return (803, 803)
