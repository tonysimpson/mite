from nanomsg import (
    Socket,
    PUB,
    RESPONDENT,
    SUB,
    SUB_SUBSCRIBE,
    SURVEYOR,
    SURVEYOR_DEADLINE,
)

import msgpack


class NanomsgProtocol:
    def __init__(self):
        self.socket = None
        self.port = None
        self.vc_location = None
        self.collector_location = None

    def open_channel_to_data_sources(self, port=9001):
        self.socket = Socket(SUB)
        self.socket.set_string_option(SUB, SUB_SUBSCRIBE, "")
        self.socket.connect("tcp://*:{}".format(port))

    def open_channel_to_collector(self, collector_location='localhost', port=9001):
        self.socket = Socket(PUB)
        self.port = port
        self.collector_location = collector_location
        self.socket.bind("tcp://{}:{}".format(self.collector_location, self.port))

    def open_channel_to_executors(self, port=9000, deadline=10000):
        self.socket = Socket(SURVEYOR)
        self.port = port
        self.socket.set_int_option(SURVEYOR, SURVEYOR_DEADLINE, deadline)
        self.socket.bind('tcp://*:{}'.format(self.port))

    def open_channel_to_vc(self, vc_location='localhost', port=9000):
        self.socket = Socket(RESPONDENT)
        self.vc_location = vc_location
        self.port = port
        self.socket.connect('tcp//{}:{}'.format(self.vc_location, self.port))

    def send(self, message):
        self.socket.send(msgpack.packb(message))

    def receive(self):
        return msgpack.unpackb(self.socket.recv())
