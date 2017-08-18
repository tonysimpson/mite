import json
import msgpack
import time
from itertools import counter

class TestMsgOutStream:
    class Context:
        def __init__(self, id, src_id, labels, parent):
            self.id = id
            self.src_id = src_id
            self.labels = dict(labels)
            if parent is not None:
                self.labels.update(parent.labels)

    def __init__(self, src_id, send_func):
        self._send = send_func
        self._src_id = src_id
        
    def new_context(self, labels_to_set, parent=None):
        return Context(id, src_id, labels_to_set, parent)

    def send_msg(self, context, type, data):
        self._send([time.time(), context.keys, context.id, context.src_id, type, data])


class TestMsgInStream:
    pass


class TestChannel:
    def __init__(self, encode, decode):
        self._transported = 0
        self._messages = []
        self._encode = encode
        self._decode = decode

    def send(self, content):
        self._messages.append(self._encode(content))

    def recv(self):
        m = self._messages.pop()
        self._transported += len(m)
        return self._decode(m)

