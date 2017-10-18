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
    -h --help           Show this screen.
    --version           Show version

"""
import asyncio
import docopt

from .datapools import DataPoolManager
from .scenariomanager import ScenarioManager
from .config import ConfigManager
from .controller import Controller
from .runner import Runner
from .utils import spec_import


class DirectRunnerTransport:
    def __init__(self, controller):
        self._controller = controller

    async def initialise(self):
        return self._controller.initialise()

    async def request_work(self, runner_id, current_work):
        return self._controller.work_request(runner_id, current_work)

    async def checkin_and_checkout(self, runner_id, datapool_id, used_list):
        return self._controller.checkin_and_checkout(runner_id, datapool_id, [dpi.id for dpi in used_list])


def scenario_test_cmd(opts):
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
    asyncio.ensure_future(Runner(transport, print).run())
    asyncio.get_event_loop().run_forever() 


def scenario_cmd(opts):
    if opts['test']:
        scenario_test_cmd(opts)


def main():
    opts = docopt.docopt(__doc__)
    if opts['scenario']:
        scenario_cmd(opts)


if __name__ == '__main__':
    main()
