"""\
Usage: dave_runner.py [options] <module_name> <csv_file> <num_users> <ramp_period>

Options:
    -h --help                  Show this screen.
    --version                  Show version.
    --cycle                    Repeat data when exhaused.
    --randomise                Randomise the data order.
    --session-per-journey      Create a new session every journey run.
    --out-socket=SOCKET        OUtput nanomsg socket [default: tcp://127.0.0.1:14501]
    --control-socket=SOCKET         
"""

import asyncio
import traceback
import random
import os
import msgpack
from itertools import cycle
import sys
import importlib
import docopt
import time
import nanomsg

__version__ = '0.0.1'

START_TIME = int(time.time() * 1000)

PID = os.getpid()

socket = nanomsg.Socket(nanomsg.PUSH)


class _TransactionContextManager:
    def __init__(self, user_session, name):
        self._user_session = user_session
        self._name = name

    def __enter__(self):
        self._user_session._start_transaction(self._name)

    def __exit__(self, *args):
        self._user_session._end_transaction()


class Session:
    def __init__(self, msg_send, test_name, journey_name):
        self._msg_send = msg_send
        self._test_name = test_name
        self._journey_name = journey_name
        self._transaction_names = []

    @property
    def _transaction_name(self):
        if self._transaction_names:
            return self._transaction_names[-1]
        else:
            return ''


    def _add_context_headers(self, msg):
        msg['journey'] = self._journey_name
        msg['test'] = self._test_name
        msg['transaction'] = self._transaction_name
        msg['time'] = time.time()

    def _add_context_headers_and_time(self, msg):
        self.__add_context_headers(msg)
        msg['time'] = time.time()

    def _send(self, _type, content):


        self.send(msgpack.dumps(msg))

    def _error(self, stacktrace):
        msg = {
            'stacktrace': stacktrace, 
            'type': 'exception'
        }
        self._add_context_headers_and_time(msg)
        self._send(msg)

    def log_error(self):
        self._error(traceback.format_exc())

    def _metrics_callback(self, metrics):
        msg = dict(metrics)
        msg['type'] = 'http_curl_metrics'
        self._add_context_headers(msg)
        self._send(msg)

    def _start_transaction(self, name):
        self._transaction_names.append(name)
        self._add_context_headers_and_time(msg)
        msg['type'] = 'start'

    def _end_transaction(self):
        name = self._transaction_names.pop()
        self._add_context_headers_and_time(msg)
        msg['type'] = 'end'

    def transaction(self, name):
        return _TransactionContextManager(self, name)


