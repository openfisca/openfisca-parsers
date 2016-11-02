#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""Lexers, parsers, compilers, etc for OpenFisca source code"""

from setuptools import setup, find_packages


classifiers = """\
Development Status :: 2 - Pre-Alpha
License :: OSI Approved :: GNU Affero General Public License v3
Operating System :: POSIX
Programming Language :: Python
Topic :: Scientific/Engineering :: Information Analysis
"""

doc_lines = __doc__.split('\n')


setup(
    name = 'OpenFisca-Parsers',
    version = '0.6.0',
    author = 'OpenFisca Team',
    author_email = 'contact@openfisca.fr',
    classifiers = [classifier for classifier in classifiers.split('\n') if classifier],
    description = doc_lines[0],
    keywords = 'benefit compiler lexer microsimulation parser social tax',
    license = 'http://www.fsf.org/licensing/licenses/agpl-3.0.html',
    long_description = '\n'.join(doc_lines[2:]),
    url = 'https://github.com/openfisca/openfisca-parsers',

    install_requires = [
        'Biryani[datetimeconv] >= 0.10.1',
        'OpenFisca-Core >= 4.0.0b1, < 5.0',
        'numpy >= 1.11',
        ],
    packages = find_packages(),
    )
