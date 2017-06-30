#!/usr/bin/env python

from setuptools import setup

def run_tests():
    from tests import suite
    return suite()

setup(
    name = 'minimalmite',
    packages=['human_curl', 'minimalmite'],
    version='0.0.1a0',
    install_requires=[
        'docopt',
        'msgpack-python',
        'pycurl',
        'chardet',
        'bs4'
    ],
    entry_points={
        'console_scripts': [
            'minimalmite = minimalmite.commands:main',
        ],
    },
    test_suite = '__main__.run_tests'
)
