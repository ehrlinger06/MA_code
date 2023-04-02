import json
import random

import gurobipy as gp
from gurobipy import GRB

import networkx as nx



# G = medG.generateGraph3()
# nodes = list(G.nodes)

substation_mapping = json.load(open('ict_substation_ied_mapping.json'))
agent_mapping = json.load(open('agent_ied_mapping.json'))
bs_substation_mapping = json.load(open('base_station_scenario1.json'))
bs_bus_connection = {}

def create_ict_graph():
    ict_graph = nx.Graph()
    # at the start of restoration, all BS-BS links are in severely degraded state and all others in slightly

    # create substations and IEDs and links
    puffer = list(substation_mapping['ied_substation'].items())
    for substation, ieds in puffer:
        ict_graph.add_node(substation, ps_in_cov=1)
        counter = 0
        for ied in ieds:
            ict_graph.add_node(ied, ps_in_cov=0)
            ict_graph.add_edge(substation, ied, link_state=2)
            counter += 1
        ict_graph.nodes[substation]['ps_in_cov'] = counter
    # create base stations, links and random bus connections
    for base_station, substations in bs_substation_mapping['BaseStation_Substation'].items():
        ict_graph.add_node(base_station, ps_in_cov=0)
        counter = 0
        for substation in substations:
            ict_graph.add_edge(base_station, substation, link_state=2)
            counter += ict_graph.nodes[substation]['ps_in_cov']
            counter += 1
        ict_graph.nodes[base_station]['ps_in_cov'] = counter
        # if there is a fixed connection for BS to bus, add this, else add randomly
        if bs_substation_mapping['BaseStation_Bus']:
            bus = bs_substation_mapping['BaseStation_Bus'][base_station]
            bs_bus_connection[base_station] = bus
        else:
            _, bus = random.choice(substations).split("_")
            bs_bus_connection[base_station] = bus

    # create bs_bs links
    for connection, nodes in bs_substation_mapping['BaseStation_BaseStation'].items():
        # delay = delays['staticDelays']['BaseStation-BaseStation']
        ict_graph.add_edge(nodes[0], nodes[1], delay=0)

    # connect agents to IEDs
    for agent, ied in agent_mapping['agent_ied'].items():
        delay = 0
        ict_graph.add_node(agent, ps_in_cov=0)
        ict_graph.add_edge(agent, ied)

    return ict_graph


def discover_terminal_nodes(G):
    terminals = []
    for node in list(G.nodes):
        if G.nodes[node]['ps_in_cov'] >= 1:
            terminals.append(node)
    return terminals


def discover_comodities(nodes, terminal_nodes):
    comm = []
    flow ={}
    already_visted = []
    non_terminal_nodes = list(set(nodes) - set(terminal_nodes))
    for node in terminal_nodes:
        counter = 0
        current_comm = f'comm_{node}'
        comm.append(current_comm)
        # already_visted.append(node)
        need_a_path_to = list(set(terminal_nodes) - set([node]))
        for dest in need_a_path_to:
            flow[(current_comm, dest)] = -10
            counter += 1
        flow[(current_comm, node)] = 10 * counter
        for non_terminal_node in non_terminal_nodes:
            flow[(current_comm, non_terminal_node)] = 0


    return comm, flow

def discover_costs(G, commodities):
    costs_dict = {}
    for commodity in commodities:
        for edge in G.edges:
            (start, dest) = edge
            costs_dict[(commodity, start, dest)] = 10
            costs_dict[(commodity, dest, start)] = 10
    return costs_dict

def discover_costs_after_first_run(G, commodities, result):
    costs_dict = {}
    for edge in result:
        for commodity in commodities:
            (start, dest) = edge
            one_capa_rounded = round(result[(start, dest)]['one'][1] * 10, 2)
            second_capa_rounded = round(result[(start, dest)]['second'][1] * 10, 2)
            costs_dict[(commodity, start, dest)] = one_capa_rounded
            costs_dict[(commodity, dest, start)] = second_capa_rounded
    return costs_dict

# def  discover_supply_demand(commodities):
#     flow = {}
#     for commodity in commodities:
#         splitted = commodity.split('_')
#         # TODO specific node combinations may have a different demand
#         flow[(commodity, int(splitted[1]))] = 30
#         flow[commodity, int(splitted[2])] = -30
#         covered_nodes = {int(splitted[1]), int(splitted[2])}
#         remaining_nodes = [ele for ele in nodes if ele not in covered_nodes]
#         for node in remaining_nodes:
#             flow[(commodity, node)] = 0
#     return flow


def discover_arc_capacity(G):
    arc_capa = {}
    for edge in G.edges:
        # TODO specific edges may have a specific capacity (agent to substation, substation to base, base to base)
        (src, dest) = edge
        arc_capa[(src, dest)] = 600
        arc_capa[(dest, src)] = 600
    return arc_capa

def check_flow_constraint(G_current=create_ict_graph()):
    G = G_current
    nodes = list(G.nodes)
    terminal_nodes = discover_terminal_nodes(G)
    commodities, inflow = discover_comodities(nodes, terminal_nodes)
    cost = discover_costs(G, commodities)
    # inflow = discover_supply_demand()
    arcs, capacity = gp.multidict(discover_arc_capacity(G))
    my_result_1 = {}
    my_result_2 = {}
    with gp.Env() as env, gp.Model(env=env) as m:
        m = gp.Model('netflow')
        flow = m.addVars(commodities, arcs, name="flow")
        m.addConstrs((flow.sum('*', i, j) <= capacity[i, j] for i, j in arcs), "cap")

        m.addConstrs(
            (flow.sum(h, '*', j) + inflow[h, j] == flow.sum(h, j, '*')
             for h in commodities for j in nodes), "node")

        m.optimize()

        if m.Status == GRB.OPTIMAL:
            my_solution_1 = m.getAttr('X', flow)
            # for h in commodities:
            #     print('\nOptimal flows for %s:' % h)
            #     for i, j in arcs:
            #         if solution[h, i, j] > 0:
            #             print('%s -> %s: %g' % (i, j, solution[h, i, j]))

            for i, j in G.edges:
                one = 0
                second = 0
                for h in commodities:
                    one += my_solution_1[h, i, j] # how much flow is there
                    second += my_solution_1[h, j, i]

                one_capa = one / capacity[(i, j)] # what part of the capacity is used
                second_capa = second / capacity[(j, i)]
                my_result_1[(i,j)] = {'one': [one, one_capa], 'second': [second, second_capa]}
            cost_2 = discover_costs_after_first_run(G, commodities, my_result_1)
            m2 = gp.Model('netflow')
            flow = m2.addVars(commodities, arcs, obj=cost_2, name="flow")
            m2.addConstrs((flow.sum('*', i, j) <= capacity[i, j] for i, j in arcs), "cap")

            m2.addConstrs(
                (flow.sum(h, '*', j) + inflow[h, j] == flow.sum(h, j, '*')
                 for h in commodities for j in nodes), "node")

            m2.optimize()

            if m2.Status == GRB.OPTIMAL:
                print("hi")
                my_solution_2 = m2.getAttr('X', flow)
                for h in commodities:
                    print('\nOptimal flows for %s:' % h)
                    for i, j in arcs:
                        if my_solution_2[h, i, j] > 0:
                            print('%s -> %s: %g' % (i, j, my_solution_2[h, i, j]))

                for i, j in G.edges:
                    one2 = 0
                    second2 = 0
                    for h in commodities:
                        one2 += my_solution_2[h, i, j]  # how much flow is there
                        second2 += my_solution_2[h, j, i]

                    one_capa2 = one2 / capacity[(i, j)]  # what part of the capacity is used
                    second_capa2 = second2 / capacity[(j, i)]
                    my_result_2[(i, j)] = {'one': [one2, one_capa2], 'second': [second2, second_capa2]}
                return True
            else:
                print("Problem")
                return False
        else:
            return False


# terminal_nodes = discover_terminal_nodes()
# commodities = discover_comodities()
# cost = discover_costs()
# inflow = discover_supply_demand()
# arcs, capacity = gp.multidict(discover_arc_capacity())
# print("hello")
#
# m = gp.Model('netflow')
#
# flow = m.addVars(commodities, arcs, obj=cost, name="flow")
# # flow = m.addVars(commodities, arcs, name="flow")
#
# # TODO find out if the flow is splitable -> It is!
# m.addConstrs((flow.sum('*', i, j) <= capacity[i, j] for i, j in arcs), "cap")
#
# m.addConstrs(
#     (flow.sum(h, '*', j) + inflow[h, j] == flow.sum(h, j, '*')
#         for h in commodities for j in nodes), "node")
#
# m.optimize()
#
# # Print solution
# if m.Status == GRB.OPTIMAL:
#     solution = m.getAttr('X', flow)
#     for h in commodities:
#         print('\nOptimal flows for %s:' % h)
#         for i, j in arcs:
#             if solution[h, i, j] > 0:
#                 print('%s -> %s: %g' % (i, j, solution[h, i, j]))

if check_flow_constraint():
    print("Success")
else:
    print("Fail")
            

