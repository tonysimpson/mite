#!/usr/bin/env python

from setuptools import setup

setup(
    name = 'mite',
    packages=['mite'],
    version='0.0.1a0',
    install_requires=[
        'docopt',
        'msgpack-python',
        'pycurl',
        'chardet',
        'bs4',
        'nanomsg'
    ],
    entry_points={
        'console_scripts': [
            'mite = mite.__main__:main',
            'mite_runner = mite.runner:main',
            'mite_data_server = mite.data_server:main',
            'mite_controller = mite.controller:main'
        ],
    },
)
