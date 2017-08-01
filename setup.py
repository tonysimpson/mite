#!/usr/bin/env python

from setuptools import setup

def run_tests():
    from tests import suite
    return suite()

setup(
    name = 'mite',
    packages=['human_curl', 'mite'],
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
            'mite = mite.commands:main',
        ],
    },
    test_suite = '__main__.run_tests'
)
