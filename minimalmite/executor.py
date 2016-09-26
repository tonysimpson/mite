from random import choice
from string import ascii_letters, digits
from minimalmite.protocols import NanomsgProtocol


class Executor:
    def __init__(self, identifier=None, controller_location="localhost", controller_port=9000, protocol=NanomsgProtocol):
        self.identifier = identifier or ''.join(choice(ascii_letters+digits) for _ in range(8))
        self.async_jobs = []
        self.sync_jobs = []
        self.vc_channel = protocol()
        self.vc_channel.open_channel_to_vc(vc_location=controller_location, port=controller_port)
        self.killed_actions = []

    def update_volumes(self):
        self.vc_channel.send("{} {} {} {}".format(
            self.identifier,
            len(self.async_jobs),
            len(self.sync_jobs),
            len(self.killed_actions)))

    def receive_jobs(self):
        pass

    def run_jobs(self):
        pass
