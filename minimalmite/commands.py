"""Minimalmite

Usage:
    minimalmite vc <package> <scenario> [--executor_port=<port>] [--collector_port=<port>]
        [--collector_location=<location>]
    minimalmite executor  [--vc_port=<port>] [--vc_location=<location>] [--collector_port=<port>]
        [--collector_location=<location>] [--max_volume=<number>]
    minimalmite collector [--listen_port=<port>]

Options:
    --executor_port=<port>          Port for the volume controller to connect to the executors on [default: 9000]
    --vc_port=<port>                Port for the executor to connect to the volume controller on [default: 9000]
    --vc_location=<location>        URL or IP where the volume controller is deployed [default: localhost]
    --listen_port=<port>            Port that the collector should listen on [default: 9001]
    --collector_port=<port>         Port for the component to send messages to the collector on [default: 9001]
    --collector_location=<location> URL or IP where the collector is deployed [default: localhost]
    --max_volume=<number>           Max number of tasks the executor should run [default: 1]
"""

from docopt import docopt
from minimalmite.executor import Executor
from minimalmite.volume_controller import VolumeController
from minimalmite.collector import Collector


def main():
    args = docopt(__doc__)
    if args['executor']:
        Executor()
    elif args['vc']:
        VolumeController(args['package'], args['scenario'], )
    elif args['collector']:
        Collector()