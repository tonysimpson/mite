#!/usr/bin/env python

from setuptools import setup

setup(
    name = 'mite',
    packages=[
        'mite',
        'mite_ctx_ext_http',
        'mite_ctx_ext_browser'
    ],
    version='0.0.1a',
    install_requires=[
        'docopt',
        'msgpack-python',
        'acurl',
        'bs4',
        'nanomsg'
    ],
    entry_points={
        'console_scripts': [
            'mite = mite.__main__:main',
        ],
    },
    setup_requires=['pytest-runner'],
    tests_require=['pytest']
)
