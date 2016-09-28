"""Minimalmite

Usage:
    minimalmite vc <package> <scenario> [--executor_port=<port>] [--collector_port=<port>] [--collector_location=<location>]
    minimalmite executor  [--vc_port=<port>] [--vc_location=<location>] [--collector_port=<port>] [--collector_location=<location>]
    minimalmite collector [--listen_port=<port>]

Options:
    --executor_port=<port>          Port for the vc to connect to the executors on
    --vc_port=<port>                Port for the executor to connect to the vc on
    --vc_location=<location>        URL or IP where the VC is deployed
    --listen_port=<port>            Port that the collector should listen on
    --collector_port=<port>         Port for the component to send messages to the collector on
    --collector_location=<location> URL or IP where the collector is deployed
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
        VolumeController()
    elif args['collector']:
        Collector()