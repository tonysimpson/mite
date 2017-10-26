"""\
Mite Load Test Framewwork.

Usage: 
    mite scenario test [options] SCENARIO_SPEC [--config=CONFIG_SPEC]

Arguments:
    SCENARIO_SPEC           Identifier for a scenario in the form package_path:callable_name
    CONFIG_SPEC             Identifier for config callable returning dict of config

Examples:
    mite scenario test mite.example:scenario

Options:
    -h --help               Show this screen.
    --version               Show version
    --log-level=LEVEL       Set logger level, one of DEBUG, INFO, WARNING, ERROR, CRITICAL [default: WARNING]
    --config=CONFIG_SPEC    Set a config loader to a callable loaded via a spec [default: mite.config:default_config_loader]

"""
import asyncio
import docopt
import threading

from .datapools import DataPoolManager
from .scenariomanager import ScenarioManager
from .config import ConfigManager
from .controller import Controller
from .runner import Runner
from .utils import spec_import, pack_msg
from .web import app, metrics_processor
import logging


class DirectRunnerTransport:
    def __init__(self, controller):
        self._controller = controller

    async def initialise(self):
        return self._controller.initialise()

    async def request_work(self, runner_id, current_work):
        return self._controller.work_request(runner_id, current_work)

    async def checkin_and_checkout(self, runner_id, datapool_id, used_list):
        return self._controller.checkin_and_checkout(runner_id, datapool_id, [dpi.id for dpi in used_list])


def _msg_handler(msg):
    metrics_processor.process_message(msg)
    if 'type' in msg and msg['type'] == 'data_created':
        open(msg['name'] + '.msgpack', 'wb+').write(pack_msg(msg['data']))
    for k, v in sorted(msg.items()):
        print("{}={}".format(k, v))
    print()


def _start_web_in_thread():
    t = threading.Thread(target=app.run, name='mite.web', kwargs={'host': '0.0.0.0', 'port': 9301})
    t.daemon = True
    t.start()


def scenario_test_cmd(opts):
    _start_web_in_thread()
    datapool_manager = DataPoolManager()
    scenario_manager = ScenarioManager(datapool_manager)
    scenario = spec_import(opts['SCENARIO_SPEC'])()
    for journey_spec, datapool_spec, volumemodel_spec in scenario:
        scenario_manager.add_scenario(journey_spec, datapool_spec, volumemodel_spec)
    config_manager = ConfigManager()
    if opts['--config'] is not None:
        config = spec_import(opts['--config'])()
        for k, v in config.items():
            config_manager.set(k, v)
    controller = Controller('test', scenario_manager, config_manager)
    transport = DirectRunnerTransport(controller)
    asyncio.ensure_future(Runner(transport, _msg_handler).run())
    asyncio.get_event_loop().run_forever() 


def scenario_cmd(opts):
    if opts['test']:
        scenario_test_cmd(opts)


def main():
    opts = docopt.docopt(__doc__)
    logging.basicConfig(level=opts['--log-level'])
    if opts['scenario']:
        scenario_cmd(opts)


if __name__ == '__main__':
    main()
