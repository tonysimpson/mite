"""\
Mite Load Test Framwwork.

Usage: 
    mite journey test [options] JOURNEY_SPEC

Arguments:
    JOURNEY_SPEC           Identifier for a journey in the form package_path:callable_name

Options:
    -h --help           Show this screen.
    --version           Show version

"""
from .runners import run_journey_spec_standalone
import docopt


def journey_test_cmd(opts):
    run_journey_spec_standalone(opts['JOURNEY_SPEC'])


def journey_cmd(opts):
    if opts['test']:
        journey_test_cmd(opts)


def main():
    opts = docopt.docopt(__doc__)
    if opts['journey']:
        journey_cmd(opts)
    print("Hello World!", opts)


if __name__ == '__main__':
    main()
