from minimalmite.protocols import NanomsgProtocol


class VolumeController:
    def __init__(self, protocol=NanomsgProtocol, executor_port=9000, deadline=10000):
        self.executors = {}
        self.banned_executors = []
        self.executor_channel = protocol()
        self.deadline = 10000
        self.executor_channel.open_channel_to_executors(port=9000, deadline=self.deadline)

    def update_volumes(self):
        identifier, async_jobs, sync_jobs, killed_actions = self.executor_channel.receive().split()
        self.executors[identifier] = [async_jobs, sync_jobs, killed_actions]