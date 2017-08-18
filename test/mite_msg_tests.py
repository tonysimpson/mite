import json
import msgpack
import time
from 

class TestMsgOutStream:
    class Context:
        def __init__(self, labels, parent):
            self.labels = dict(labels)
            if parent is not None:
                self.labels.update(parent.labels)

    def __init__(self, send_func):
        self._send = send_func
        
    def new_context(self, labels_to_set, parent=None):
        return Context(labels_to_set, parent)

    def send_msg(self, context, type, data):
        self._send([time.time(), context.keys, context.id, type, data])


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

