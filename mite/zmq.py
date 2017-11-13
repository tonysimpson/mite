import zmq

from .utils import pack_msg, unpack_msg
import asyncio
import logging

logger = logging.getLogger(__name__)


class ZMQSender:
    def __init__(self, socket_address):
        self._zmq_context = zmq.Context()
        self._sock = self._zmq_context.socket(zmq.PUSH)
        self._sock.connect(socket_address)

    def send(self, msg):
        self._sock.send(pack_msg(msg))


class ZMQReceiver:
    def __init__(self, socket_address, listeners=None, raw_listeners=None, loop=None):
        self._zmq_context = zmq.Context()
        self._sock = self._zmq_context.socket(zmq.PULL)
        self._sock.bind(socket_address)
        if listeners is None:
            listeners = []
        self._listeners = listeners
        if raw_listeners is None:
            raw_listeners = []
        self._raw_listeners = raw_listeners
        if loop is None:
            loop = asyncio.get_event_loop()
        self._loop = loop

    def add_listener(self, listener):
        self._listeners.append(listener)
    
    def add_raw_listener(self, listener):
        self._raw_listeners.append(listener)

    def _recv(self):
        return self._sock.recv()

    async def run(self, stop_func=None):
        return await self._loop.run_in_executor(None, self._run, stop_func)

    def _run(self, stop_func=None):
        while stop_func is None or not stop_func():
            raw = self._recv()
            for raw_listener in self._raw_listeners:
                raw_listener(raw)
            msg = unpack_msg(raw)
            for listener in self._listeners:
                listener(msg)


_MSG_TYPE_HELLO = 1
_MSG_TYPE_REQUEST_WORK = 2
_MSG_TYPE_BYE = 3


class ZMQRunnerTransport:
    def __init__(self, socket_address, loop=None):
        self._zmq_context = zmq.Context()
        self._sock = self._zmq_context.socket(zmq.REQ)
        self._sock.connect(socket_address)
        if loop is None:
            loop = asyncio.get_event_loop()
        self._loop = loop

    def _hello(self):
        self._sock.send(pack_msg((_MSG_TYPE_HELLO, None)))
        return unpack_msg(self._sock.recv())

    async def hello(self):
        return await self._loop.run_in_executor(None, self._hello)

    def _request_work(self, runner_id, current_work, completed_data_ids, max_work):
        logger.debug('socket send')
        self._sock.send(pack_msg((_MSG_TYPE_REQUEST_WORK, [runner_id, current_work, completed_data_ids, max_work])))
        logging.debug('socket receive')
        result = unpack_msg(self._sock.recv())
        logging.debug('done') 
        return result

    async def request_work(self, runner_id, current_work, completed_data_ids, max_work):
        return await self._loop.run_in_executor(None, self._request_work, runner_id, current_work, completed_data_ids, max_work)

    def _bye(self, runner_id):
        self._sock.send(pack_msg((_MSG_TYPE_BYE, runner_id)))
        return unpack_msg(self._sock.recv())

    async def bye(self, runner_id):
        return await self._loop.run_in_executor(None, self._request_work, runner_id)


class ZMQControllerServer:
    def __init__(self, socket_address):
        self._zmq_context = zmq.Context()
        self._sock = self._zmq_context.socket(zmq.REP)
        self._sock.bind(socket_address)

    async def run(self, controller, stop_func=None):
        while stop_func is None or not stop_func():
            _type, content = unpack_msg(self._sock.recv())
            if _type == _MSG_TYPE_HELLO:
                self._sock.send(pack_msg(controller.hello()))
            elif _type == _MSG_TYPE_REQUEST_WORK:
                self._sock.send(pack_msg(controller.request_work(*content)))
            elif _type == _MSG_TYPE_BYE:
                self._sock.send(pack_msg(controller.bye(content)))

