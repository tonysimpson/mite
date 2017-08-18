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

from mite.session import Session
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


class UserSession:
    def __init__(self, socket, test_name, journey_name):
        self._http_session = Session(metrics_callback=self._metrics_callback)
        self._socket = socket
        self._test_name = test_name
        self._journey_name = journey_name
        self._transaction_names = []

    @property
    def transaction_name(self):
        if self._transaction_names:
            return self._transaction_names[-1]
        else:
            return ''

    def post(self, *args, **kwargs):
        self._http_session.post(*args, **kwargs

    def get(self, *args, **kwargs):
        self._http_session.get(*args, **kwargs)

    def head(self, *args, **kwargs):
        self._http_session.head(*args, **kwargs)

    def options(self, *args, **kwargs):
        self._http_session.options(*args, **kwargs)

    def put(self, *args, **kwargs):
        self._http_session.put(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        self._http_session.delete(*args, **kwargs)  

    def _add_context_headers(self, msg):
        msg['journey'] = self._journey_name
        msg['test'] = self._test_name
        msg['transaction'] = self.transaction_name

    def _add_context_headers_and_time(self, msg):
        self.__add_context_headers(msg)
        msg['time'] = time.time()

    def _send(self, msg):
        self._socket.send(msgpack.dumps(msg))

    def _error(self, stacktrace):
        msg = {
            'stacktrace': stacktrace, 
            'type': 'exception'
        }
        self._add_context_headers_and_time(msg)
        self._send(msg)

    def send_msg(self, type, content):
        msg = dict(content)
        msg['type'] = type;
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


async def runner(delay, test_name, journey_name, journey, journey_args, fresh_session):
    print('Starting runner with delay {}'.format(delay))
    await asyncio.sleep(delay)
    session = UserSession(socket, test_name, journey_name)
    for args in journey_args:
        try:
            with session.transaction('JOURNEY'):
                await journey(session, *args)
        except Exception as e:
            session.log_error()
        if fresh_session:
            session = UserSession(socket, test_name, journey_name)


def main(argv):
    opts = docopt.docopt(__doc__, argv=argv, version=__version__)
    socket.connect(opts['--out-socket'])
    module_name = opts['<module_name>']
    csv_file = opts['<csv_file>']
    num_users = int(opts['<num_users>'])
    ramp_period = float(opts['<ramp_period>'])
    journey_args = [[col.strip() for col in line.split(',')] for line in open(csv_file)]
    if opts['--randomise']:
        random.shuffle(journey_args)
    if opts['--cycle']:
        journey_args = cycle(journey_args)
    else:
        journey_args = iter(journey_args)
    journey = importlib.import_module(module_name).journey
    loop = asyncio.get_event_loop()
    runners = []
    for i in range(num_users):
        delay = i * (ramp_period / num_users)
        runners.append(runner(delay, journey, journey_args, opts['--session-per-journey']))
    loop.run_until_complete(asyncio.gather(*runners))


if __name__ == '__main__':
    main(sys.argv[1:])
