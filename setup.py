#!/usr/bin/env python

from distutils.core import setup

import tarwalker

name = 'tarwalker'
url = 'https://github.com/n2vram/' + name

setup(
    name=name,
    version=tarwalker.version,
    description=tarwalker.description,
    long_description=open('README.rst').read(),
    license='MIT',
    author='NVRAM',
    author_email='nvram@users.sourceforge.net',
    url=url,
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Topic :: Text Processing :: Filters',
        'Topic :: Utilities',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    keywords=['argparse', 'numparser', 'parser', 'numbers', 'parsing',
              'ArgumentParser', 'command-line', 'sequences'],

    py_modules=[name],
    download_url=(url + '/archive/' + tarwalker.version),
    platforms=['any'],
)
