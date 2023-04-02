import os
import json
import networkx as nx
import random
import copy

from blackstart.blackstart_ict.graphStuff import updateGraph_by_availbuses, filter_bs_from_graph
from blackstart.blackstart_ict.geneticAlgo import runner, showGraphByDesign


class ICTModel:
    """A model to handle a networkX graph for the ICT system."""

    def __init__(self, scenario_name, bs_batteries, bs_numbers, bc_capable_buses):
        folder_name = scenario_name
        bs_number_scenario = bs_numbers
        self.bs_batteries = bs_batteries
        self.bc_capable_buses = bc_capable_buses

        # load files
        this_folder = os.path.dirname(os.path.abspath(__file__))
        agent_mapping_file = os.path.join(this_folder, 'ict_data', folder_name, 'agent_ied_mapping.json')
        substation_mapping_file = os.path.join(this_folder, 'ict_data', folder_name,
                                               'ict_substation_ied_mapping.json')
        bs_substation_mapping_file = os.path.join(this_folder, 'ict_data', folder_name, bs_number_scenario + '.json')
        delays_file = os.path.join(this_folder, 'ict_data', folder_name, 'delays.json')

        agent_mapping = open(agent_mapping_file)
        self.agent_mapping = json.load(agent_mapping)

        substation_mapping = open(substation_mapping_file)
        self.substation_mapping = json.load(substation_mapping)

        bs_substation_mapping = open(bs_substation_mapping_file)
        self.bs_substation_mapping = json.load(bs_substation_mapping)

        delays = open(delays_file)
        self.delays = json.load(delays)

        # random parameters
        self.bs_bus_connection = {}
        self.bs_battery_mapping = {}
        # graph parameters
        self.initial_ict_graph = self.create_ict_graph()
        #print("initial_ict_graph:")
        #print(self.initial_ict_graph.nodes)
        self.current_buses = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
        
        # otimize
        self.ga_result = runner(len(self.initial_ict_graph.nodes), self.initial_ict_graph)
        
        best_solution = self.ga_result.X[0].tolist()
        self.graph_for_best_solution = showGraphByDesign(des=best_solution)
        print("graph_for_best_solution:")
        print(self.graph_for_best_solution.nodes)

        # parameters for other simulators
        self.current_ict_graph = self.initial_ict_graph
        self.current_ICT_ranks = None
        self.optimal_ict_graph = filter_bs_from_graph(self.graph_for_best_solution)
        # self.optimal_ict_graph = None

    def create_ict_graph(self):
        ict_graph = nx.Graph()
        # at the start of restoration, all BS-BS links are in severely degraded state and all others in slightly

        # create substations and IEDs and links
        for substation, ieds in self.substation_mapping['ied_substation'].items():
            ict_graph.add_node(substation)
            for ied in ieds:
                ict_graph.add_node(ied)
                delay = self.delays['staticDelays']['SubStation-IED']
                ict_graph.add_edge(substation, ied, delay=delay)

        # create base stations, links and bus connections
        for base_station, substations in self.bs_substation_mapping['BaseStation_Substation'].items():
            ict_graph.add_node(base_station, ps_in_cov=0)
            counter = 0
            for substation in substations:
                # delay = self.delays['staticDelays']['BaseStation-SubStation']
                delay = 0
                ict_graph.add_edge(base_station, substation, delay=delay)
                counter += 1
            ict_graph

            # create bs_bus connections
            bus = self.bs_substation_mapping['BaseStation_Bus'][base_station]
            self.bs_bus_connection[base_station] = bus

        # create bs_bs links
        for connection, nodes in self.bs_substation_mapping['BaseStation_BaseStation'].items():
            # delay = self.delays['staticDelays']['BaseStation-BaseStation']
            delay = 0
            ict_graph.add_edge(nodes[0], nodes[1], delay=delay)

        # connect agents to IEDs
        for agent, ied in self.agent_mapping['agent_ied'].items():
            delay = 0
            ict_graph.add_node(agent)
            ict_graph.add_edge(agent, ied, delay=delay)

        # place random batteries
        number_of_batteries = round(len(self.bs_substation_mapping['BaseStation_Substation']) * self.bs_batteries)
        number_of_bc_buses = len(self.bc_capable_buses)
        bs_with_batteries = []
        list_of_bs = list(self.bs_substation_mapping['BaseStation_Substation'])

        # first find bs at bc capable buses
        for bus in self.bc_capable_buses:
            for bs, bus_number in self.bs_substation_mapping['BaseStation_Bus'].items():
                if bus_number == bus:
                    bs_with_batteries.append(bs)
                    list_of_bs.remove(bs)

        # then place the rest of the batteries random at other buses (if there are any batteries left)
        if number_of_batteries-number_of_bc_buses > 0:
            random_bs = random.sample(list_of_bs, number_of_batteries - number_of_bc_buses)
            bs_with_batteries.extend(random_bs)

        for base_station in self.bs_substation_mapping['BaseStation_Substation'].keys():
            if base_station in list(set(bs_with_batteries)):
                self.bs_battery_mapping[base_station] = True
            else:
                self.bs_battery_mapping[base_station] = False

        return ict_graph

    def step(self, available_buses):
        """Update the current ICT graph with available buses

        """
        print("Hi from internal step in ICT restoration")
        print(available_buses)
        # new_ict_graph = copy.deepcopy(self.initial_ict_graph)
        new_ict_graph, new_current_buses = updateGraph_by_availbuses(self.current_ict_graph, self.graph_for_best_solution, self.current_buses, available_buses, self.bs_substation_mapping, self.substation_mapping, self.agent_mapping)
        self.current_buses = new_current_buses
        #print("####################### START GRAPH OUTPUT ICT")
        #print(new_ict_graph.nodes)
        #print(new_ict_graph.edges)
        #print("####################### end GRAPH OUTPUT ICT")

        self.current_ict_graph = new_ict_graph
        # print("skipping graph asignment")
