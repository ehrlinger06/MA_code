import mosaik_api
import logging
import copy
LOG = logging.getLogger(__name__)
from blackstart.blackstart_ict.model import ICTModel
from blackstart.blackstart_ict.message_pb2 import InfrastructureMessage

META = {
    'type':'time-based',
    'models': {
        'ICTModel': {
            'public': True,
            'params': ['scenario_name', 'bs_batteries', 'bs_numbers', 'bc_capable_buses'],
            'attrs': ['current_ict_graph', 'optimal_ict_graph', 'available_buses', 'ict_message', 'ctrl_message']
        }
    },
}


class ICTSimulator(mosaik_api.Simulator):

    def __init__(self):
        super().__init__(META)
        self.sid = None
        self.step_size = 0
        self.scenario_name = None
        self.bs_batteries = 0
        self.bs_numbers = None
        self.bc_capable_buses = None
        self.models = dict()
        self.time = 0

    def init(self, sid, **sim_params):
        """Called exactly once after the simulator has been started.

        :return: the meta data dict (set by mosaik_api.Simulator)
        """
        # simulator parameters
        self.sid = sid
        self.step_size = sim_params['step_size']

        return self.meta

    def create(self, num, model, **model_params):
        entities = []

        if model == "ICTModel":
            for i in range(num):
                eid = '{}-{}'.format(model, len(self.models))

                self.models[eid] = ICTModel(model_params['scenario_name'], model_params['bs_batteries'],
                                            model_params['bs_numbers'], model_params['bc_capable_buses'])

                entities.append({'eid': eid, 'type': model})
        return entities

    def step(self, time, inputs, max_advance):
        LOG.debug("At step %d received inputs %s", time, inputs)
        print("Hi from external step in ICT restoration")
        print(time)
        self.time = time
        # hand over information from MAS to ICT model and step ICT model
        for eid, attrs in inputs.items():
            for attr, src_ids in attrs.items():
                if attr == 'available_buses':
                    for src_id, value in src_ids.items():
                        self.models[eid].step(value)

        return time + self.step_size

    def get_data(self, outputs):
        # get updated ICT graph and ICT ranks
        data = {}
        for eid, attrs in outputs.items():
            data[eid] = {}
            for attr in attrs:
                if attr == 'current_ict_graph':
                    data[eid][attr] = copy.deepcopy(self.models[eid].current_ict_graph)
                    
                elif attr == 'optimal_ict_graph':
                    data[eid][attr] = copy.deepcopy(self.models[eid].optimal_ict_graph)
                elif attr == 'ict_message':
                    if self.time == 60:  
                        data[eid][attr] = [{
                        'msg_type': InfrastructureMessage.MsgType.DISCONNECT,
                        'msg_id': f'ICTControllerDisconnect_0',
                        'sim_time': 120,
                        'change_module': 'router2'
                        }]
                    elif self.time == 120:
                        data[eid][attr] = [{
                        'msg_type': InfrastructureMessage.MsgType.DISCONNECT,
                        'msg_id': f'ICTControllerDisconnect_1',
                        'sim_time': 300,
                        'change_module': 'router3 '
                        }]
                    else:
                        data[eid][attr] = [] 
        LOG.debug("Gathered outputs %s", data)
        return data
