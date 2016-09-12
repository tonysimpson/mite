from nanomsg import *
import msgpack
import docopt

class ActivityGroupVolumeManager:
    def started(self, elapsed_time, activity_id):
        pass
    
    def finished(self, elapsed_time, activity_id):
        pass

    def calculate_required_change(self, elapsed_time):
        pass


class Activity:
    def __init__(self, activity_id, activity_name, params):



class ActivitySource:
    def get_next_free_activity(self):
        pass

    def return_activity(self, activity, errored):
        pass



class ActivityGroup:
    def __init__(self, group_name, activity_group_volume_manager, activity_source, node_matcher):
        self.activity_group_volume_manager = activity_group_volume_manager
        self.activity_source = activity_source
        self.node_matcher = node_matcher



def volume_controller():
    reply_channel = Socket(REP)
    while True:
        msg = reply_channel.recv()
        msg_data = msgpack.unpack(msg)
        mtype, mparams = msg_data['type'], msg_data['params']
        if mtype == 'set_state':
            pass
        elif mtype == 'load_info':
            pass
        elif mtype == 'work_request':
            pass
        elif mtype == 'register':
            pass
        elif mtype == 'kick_activity':
            pass
        elif mtype == 'kill_activity':
            pass
        elif mtype == 


