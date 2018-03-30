#!/bin/bash
set -ex

# From: 'pip install flake8'
python2 -m flake8 *.py */*.py
python3 -m flake8 *.py */*.py

# Test with Python2.7+ and Python3.x
python2 -m pytest -vvv --cov-report=term-missing --cov=tarwalker
python3 -m pytest -vvv --cov-report=term-missing --cov=tarwalker

# Validate the README.rst file.  On F21, "rst2html" is part of "python-docutils".
rst2html --cloak-email-addresses --compact-lists --no-raw --smart-quotes=no \
	 README.rst > /tmp/README.html

