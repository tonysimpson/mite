"""\
Usage: dave_runner.py [options] <module_name> <csv_file> <num_users> <ramp_period>

Options:
    -h --help                  Show this screen.
    --version                  Show version.
    --out-socket=SOCKET        OUtput nanomsg socket [default: tcp://127.0.0.1:14501]
    --control-socket=SOCKET    Controller nanomsg socket [default: tcp://127.0.0.1:14500]
"""

from mite.session import Session
import asyncio
import os
import msgpack
from itertools import cycle
import sys
import importlib
import docopt
import time


class ArgsClient:


class Runner:
    def __init__(self, out_socket, args_block_size=100):
        self._out_socket = out_socket
        self._args_block_size = args_block_size

    async def _take_journey_args(self, name):

    async def _give_journey_args(self, name, args):

    def _get_journey_func(self, journey_specifier):
        journey_module_name, journey_function_name = journey_specifier.split(':')
        journey_module = importlib.import_module(journey_module_name)
        journey_function = getattr(journey_module, journey_function_name)
        return journey_function

    async def _run(self, test_name, journey_specifier, journey_args_name, reset_session, control):
        session = Session(self._out_socket, test_name, journey_specifier, control)
        journey_function = self._get_journey_func(journey_specifier)
        while not session.should_stop:
            args = await self._take_journey_args(journey_args_name)
            try:
                with session.transaction(journey_specifier):
                    await journey_function(session, *args)
            except Exception as e:
                session.log_error()
            await self._give_journey_args(journey_args_name, args)
            if reset_session:
                session.reset()



def main(argv):
    opts = docopt.docopt(__doc__, argv=argv, version=__version__)
    socket.connect(opts['--out-socket'])

    module_name = opts['<module_name>']
    journey = importlib.import_module(module_name).journey
    loop = asyncio.get_event_loop()
    runners = []
    for i in range(num_users):
        delay = i * (ramp_period / num_users)
        runners.append(runner(delay, journey, journey_args, opts['--session-per-journey']))
    loop.run_until_complete(asyncio.gather(*runners))


if __name__ == '__main__':
    main(sys.argv[1:])
