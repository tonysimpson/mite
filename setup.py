from setuptools import setup

setup(
    name = 'minimalmite',
    packages=['minimalmite'],
    version='0.0.1a0',
    install_requires=[
        'docopt',
        'msgpack-python',
        'human_curl',
        'pycurl'
    ],
    entry_points={
        'console_scripts': [
            'minimalmite = minimalmite.commands:main',
        ],
    }
)
