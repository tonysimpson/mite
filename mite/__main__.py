"""\
Mite Load Test Framewwork.

Usage:
    mite [options] scenario test SCENARIO_SPEC [--config=CONFIG_SPEC]
    mite [options] journey test JOURNEY_SPEC [DATAPOOL_SPEC] [--volume=VOLUME]
    mite controller SCENARIO_SPEC [--config=CONFIG_SPEC] [--controller-socket=SOCKET] [--message-socket=SOCKET] [--delay-start-seconds=DELAY]
    mite runner [--controller-socket=SOCKET] [--message-socket=SOCKET]
    mite collector [--message-socket=SOCKET] [--web-address=HOST_POST] [--no-web]
    mite --help
    mite --version

Arguments:
    SCENARIO_SPEC           Identifier for a scenario in the form package_path:callable_name
    CONFIG_SPEC             Identifier for config callable returning dict of config
    JOURNEY_SPEC            Identifier for journey async callable
    VOLUME_MODEL_SPEC       Identifier for volume model callable

Examples:
    mite scenario test mite.example:scenario

Options:
    -h --help                       Show this screen
    --version                       Show version
    --log-level=LEVEL               Set logger level, one of DEBUG, INFO, WARNING, ERROR, CRITICAL [default: INFO]
    --config=CONFIG_SPEC            Set a config loader to a callable loaded via a spec [default: mite.config:default_config_loader]
    --no-web                        Don't start the build in webserver
    --spawn-rate=NUM_PER_SECOND     Maximum spawn rate [default: 1000]
    --max-loop-delay=SECONDS        Runner internal loop delay maximum [default: 1]
    --min-loop-delay=SECONDS        Runner internal loop delay minimum [default: 0.01]
    --runner-max-journeys=NUMBER    Max number of concurrent journeys a runner can run
    --controller-socket=SOCKET      Controller socket [default: tcp://127.0.0.1:14301]
    --message-socket=SOCKET         Message socket [default: tcp://127.0.0.1:14302]
    --delay-start-seconds=DELAY     Delay start allowing others to connect [default: 10]
    --volume=VOLUME                 Volume to run journey at [default: 1]
    --web-address=HOST_POST         Web bind address [default: 127.0.0.1:9301]

"""
import asyncio
import docopt
import threading

from .scenario import ScenarioManager
from .config import ConfigManager
from .controller import Controller
from .runner import Runner
from .collector import Collector
from .utils import spec_import, pack_msg
from .web import app, metrics_processor
from .nanomsg import NanomsgSender, NanomsgReciever, NanomsgRunnerTransport, NanomsgControllerServer
import logging


class DirectRunnerTransport:
    def __init__(self, controller):
        self._controller = controller

    async def hello(self):
        return self._controller.hello()

    async def request_work(self, runner_id, current_work, completed_data_ids, max_work):
        return self._controller.request_work(runner_id, current_work, completed_data_ids, max_work)

    async def bye(self, runner_id):
        return self._controller.bye(runner_id)


msg_logger = logging.getLogger('MSG')
def _msg_handler(msg):
    metrics_processor.process_message(msg)
    if 'type' in msg and msg['type'] == 'data_created':
        open(msg['name'] + '.msgpack', 'ab').write(pack_msg(msg['data']))
    start = "[%s] %.6f" % (msg.pop('type', None), msg.pop('time', None))
    end = ', '.join("%s=%r" % (k, v) for k, v in msg.items() if k != 'stacktrace')
    msg_logger.info("%s %s", start, end)
    if 'stacktrace' in msg:
        msg_logger.warning(msg['stacktrace'])


def _maybe_start_web_in_thread(opts):
    if opts['--no-web']:
        return
    address = opts['--web-address']
    kwargs = {'port': 9301}
    if address.startswith('['):
            # IPV6 [host]:port
        if ']:' in address:
            host, port = address.split(']:')
            kwargs['host'] = host[1:]
            kwargs['port'] = int(port)
        else:
            kwargs['host'] = address[1:-1]
    elif address.count(':') == 1:
        host, port = address.split(':')
        kwargs['host'] = host
        kwargs['port'] = int(port)
    else:
        kwargs['host'] = address
    t = threading.Thread(target=app.run, name='mite.web', kwargs=kwargs)
    t.daemon = True
    t.start()


def _create_config_manager(opts):
    config_manager = ConfigManager()
    config = spec_import(opts['--config'])()
    for k, v in config.items():
        config_manager.set(k, v)
    return config_manager


def _create_runner(opts, transport, msg_sender):
    loop_wait_max = float(opts['--max-loop-delay'])
    loop_wait_min = float(opts['--min-loop-delay'])
    max_work = None
    if opts['--runner-max-journeys']:
        max_work = int(opts['--runner-max-journeys'])
    return Runner(transport, msg_sender, loop_wait_min=loop_wait_min, loop_wait_max=loop_wait_max, max_work=max_work)


def _create_scenario_manager(opts):
    return ScenarioManager(start_delay=float(opts['--delay-start-seconds']), period=float(opts['--max-loop-delay']), min_period=float(opts['--min-loop-delay']), spawn_rate=int(opts['--spawn-rate']))


def test_scenarios(test_name, opts, scenarios):
    _maybe_start_web_in_thread(opts)
    scenario_manager = _create_scenario_manager(opts)
    for journey_spec, datapool, volumemodel in scenarios:
        scenario_manager.add_scenario(journey_spec, datapool, volumemodel)
    config_manager = _create_config_manager(opts)
    controller = Controller(test_name, scenario_manager, config_manager)
    transport = DirectRunnerTransport(controller)
    asyncio.get_event_loop().run_until_complete(_create_runner(opts, transport, _msg_handler).run())


def scenario_test_cmd(opts):
    scenario_spec = opts['SCENARIO_SPEC']
    scenarios = spec_import(scenario_spec)()
    test_scenarios(scenario_spec, opts, scenarios)


def journey_test_cmd(opts):
    journey_spec = opts['JOURNEY_SPEC']
    datapool_spec = opts['DATAPOOL_SPEC']
    if datapool_spec:
        datapool = spec_import(datapool_spec)
    else:
        datapool = None
    volumemodel = lambda start, end: int(opts['--volume'])
    test_scenarios(journey_spec, opts, [(journey_spec, datapool, volumemodel)])


def scenario_cmd(opts):
    if opts['test']:
        scenario_test_cmd(opts)


def journey_cmd(opts):
    if opts['test']:
        journey_test_cmd(opts)


def controller(opts):
    scenario_spec = opts['SCENARIO_SPEC']
    scenarios = spec_import(scenario_spec)()
    scenario_manager = _create_scenario_manager(opts)
    for journey_spec, datapool, volumemodel in scenarios:
        scenario_manager.add_scenario(journey_spec, datapool, volumemodel)
    config_manager = _create_config_manager(opts)
    controller = Controller(scenario_spec, scenario_manager, config_manager)
    server = NanomsgControllerServer(opts['--controller-socket'])
    asyncio.get_event_loop().run_until_complete(server.run(controller, controller.should_stop))


def runner(opts):
    transport = NanomsgRunnerTransport(opts['--controller-socket'])
    sender = NanomsgSender(opts['--message-socket'])
    asyncio.get_event_loop().run_until_complete(_create_runner(opts, transport, sender.send).run())


def collector(opts):
    _maybe_start_web_in_thread(opts)
    reciever = NanomsgReciever(opts['--message-socket'])
    collector = Collector()
    reciever.add_listener(metrics_processor.process_message)
    reciever.add_listener(collector.process_message)
    reciever.add_raw_listener(collector.process_raw_message)
    asyncio.get_event_loop().run_until_complete(reciever.run())


def main():
    opts = docopt.docopt(__doc__)
    logging.basicConfig(
        level=opts['--log-level'],
        format='[%(asctime)s] <%(levelname)s> [%(name)s] [%(pathname)s:%(lineno)d %(funcName)s] %(message)s')
    if opts['scenario']:
        scenario_cmd(opts)
    elif opts['journey']:
        journey_cmd(opts)
    elif opts['controller']:
        controller(opts)
    elif opts['runner']:
        runner(opts)
    elif opts['collector']:
        collector(opts)


if __name__ == '__main__':
    main()
