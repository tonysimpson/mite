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
        'bs4'
    ],
    entry_points={
        'console_scripts': [
            'mite = mite.__main__:main',
        ],
    },
)
