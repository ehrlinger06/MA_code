import copy
import json
import random

from matplotlib import pyplot as plt

import networkx as nx

from blackstart.blackstart_ict.message_pb2 import InfrastructureMessage

bs_bus_connection = {}

def create_ict_graph(substation_mapping, bs_substation_mapping):
    ict_graph = nx.Graph()
    # at the start of restoration, all BS-BS links are in severely degraded state and all others in slightly

    # create substations and IEDs and links
    puffer = list(substation_mapping['ied_substation'].items())
    for substation, ieds in puffer:
        ict_graph.add_node(substation, ps_in_cov=0)
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

    for connection, nodes in bs_substation_mapping['BaseStation_BaseStation'].items():
        ict_graph.add_edge(nodes[0], nodes[1], link_state=3)

    # start my code
    # TODO delete when not needed any more
    done = True
    if not done:
        pos = nx.spring_layout(ict_graph, seed=7)
        nx.draw(ict_graph, pos)
        plt.savefig("graph_1.pdf")
        plt.show()
        done = True
    return ict_graph

def add_inter_bs_connections(network, bs_substation_mapping):
    mapping = bs_substation_mapping["BaseStation_BaseStation"]
    for link in mapping.keys():
        if mapping[link][0] in list(network.nodes) and mapping[link][1] in list(network.nodes):
            network.add_edge(mapping[link][0], mapping[link][1])
    return network


def add_subsations_bs_connections(new_bss, network, bs_substation_mapping):
    currently_active_substations2 = []
    mapping = bs_substation_mapping["BaseStation_Substation"]
    for bs in mapping.keys():
        if bs in new_bss:
            potential_subs = mapping[bs]
            counter = 0
            for potential_sub in potential_subs:
                network.add_node(potential_sub, ps_in_cov=0)
                network.add_edge(bs, potential_sub)
                currently_active_substations2.append(potential_sub)
                counter += 1
                # TODO send connect command to cosima for agent(substation)
            network.nodes[bs]['ps_in_cov'] = counter
    return currently_active_substations2, network


def get_ieds_for_substation(cu_susa, substation_mapping):
    mapping = substation_mapping['ied_substation']
    currently_active_substations_dict = {}
    for substation in cu_susa:
        currently_active_substations_dict[substation] = mapping[substation]
    return currently_active_substations_dict


def add_agents_to_substations(network, cu_susa, substation_mapping):
    cu_susa_dict = get_ieds_for_substation(cu_susa, substation_mapping)
    for key, ieds in cu_susa_dict.items():
        counter = 0
        for ied in ieds:
            # agent = find_agent_via_ied(ied)
            network.add_node(ied, ps_in_cov=0)
            network.add_edge(key, ied)
            counter += 1
            # TODO send connect command to cosima for agent(load, DER, switch)
        network.nodes[key]['ps_in_cov'] = counter
    return network

def filter_newly_added_buses(current_buses, available_buses):
    newly_added = []
    for entry in available_buses:
        if entry not in current_buses:
            newly_added.append(entry)
    return newly_added


def filter_newly_removed_buses(current_buses, available_buses):
    newly_removed = []
    for entry in current_buses:
        if entry not in available_buses:
            newly_removed.append(entry)
    return newly_removed
    
def update_ps_in_cov(new_bss, network, bs_substation_mapping):
    mapping = bs_substation_mapping["BaseStation_Substation"]
    for bs in new_bss:
        counter = 0
        for substation in mapping[bs]:
            counter += network.nodes[substation]['ps_in_cov']
            counter += 1
        network.nodes[bs]['ps_in_cov'] = counter
    return network
    
def add_stations_for_new_buses(network,optimal_network, new_buses, bs_substation_mapping, substation_mapping, agent_mapping):
    # test if new bs
    bs_to_bus_mapping = bs_substation_mapping["BaseStation_Bus"]
    added_bs_list = []
    for bs, bus in bs_to_bus_mapping.items():
        if bus in new_buses:
            # if optimal_network.has_node(bs):
            if True:
                network.add_node(bs, ps_in_cov=0)
                # TODO send connect command to cosima for agent(bs)
                added_bs_list.append(bs)
    # check if new inter bs connections needed, if yes, add new connections, if no, do nothing
    if len(added_bs_list) > 0:
        # network2 = add_inter_bs_connections(network, bs_substation_mapping)
        # TODO check in BS with BC for inter BS connections
        mapping = bs_substation_mapping["BaseStation_BaseStation"]
        for link in mapping.keys():
            if mapping[link][0] in list(network.nodes) and mapping[link][1] in list(network.nodes):
                network.add_edge(mapping[link][0], mapping[link][1])
    # find new substations
    newly_active_substations = {}
    newly_active_agents = []
    # newly_active_substations, newly_active_agents = get_ieds_from_agents(bus_list=new_buses)
    newly_active_substations, network3 = add_subsations_bs_connections(added_bs_list, network, bs_substation_mapping)
    network4 = add_agents_to_substations(network3, newly_active_substations, substation_mapping)
    network5 = update_ps_in_cov(added_bs_list, network4, bs_substation_mapping)
    
    for agent, ied in agent_mapping['agent_ied'].items():
        if network5.has_node(ied):
            network5.add_node(agent)
            network5.add_edge(agent, ied)
    
    return network5
    
def remove_stations_for_removed_buses(network, removed_busses, bs_substation_mapping):
    # remove base stations
    mapping = bs_substation_mapping["BaseStation_Bus"]
    for bs in mapping.keys():
        if mapping[bs] in removed_busses:
            network.remove_node(bs) 
            # TODO send disconnect command to cosima for agent(basestation)
    # remove substations no longer connected to a basestation
    nodes_copy = {}
    nodes_copy = copy.deepcopy(network.nodes())
    for node in nodes_copy:
        if 'SubStation' in node:
            # abc = network.neighbors(node)
            keep = False
            neighbour_list = list(network.neighbors(node))
            for neigh in neighbour_list:
                if "Base" in neigh:
                    keep = True
            if not keep:
                network.remove_node(node)
                # TODO send disconnect command to cosima for agent(substation)
                for n in neighbour_list:
                    neighbour_of_n = list(network.neighbors(n))
                    network.remove_node(n)
                    for i in neighbour_of_n:
                        if 'agent' in i:
                            network.remove_node(i)
                    # TODO send disconnect command to cosima for agent(load, DER, switch)
        
    return network
    
def updateGraph_by_availbuses(current_network, optimal_network, current_buses, available_buses, bs_substation_mapping, substation_mapping, agent_mapping):
    new_buses = filter_newly_added_buses(current_buses, available_buses)
    #print("new_buses")
    #print(new_buses)
    removed_busses = filter_newly_removed_buses(current_buses, available_buses)
    #print("removed_busses")
    #print(removed_busses)
    network2 = add_stations_for_new_buses(current_network, optimal_network, new_buses, bs_substation_mapping, substation_mapping, agent_mapping)
    network3 = remove_stations_for_removed_buses(network2, removed_busses, bs_substation_mapping)
    [current_buses.append(n) for n in new_buses]
    [current_buses.remove(n) for n in removed_busses]
    
    return network3, current_buses
    
def filter_bs_from_graph(graph):
    bs_list = []
    for node in graph.nodes:
        if 'Base' in node:
            bs_lst.append(node)
    bs_graph = graph.subgraph(bs_list).copy()
    return bs_graph

