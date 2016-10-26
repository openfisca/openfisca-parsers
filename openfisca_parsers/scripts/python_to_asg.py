#! /usr/bin/env python
# -*- coding: utf-8 -*-


# OpenFisca -- A versatile microsimulation software
# By: OpenFisca Team <contact@openfisca.fr>
#
# Copyright (C) 2011, 2012, 2013, 2014, 2015, 2016 OpenFisca Team
# https://github.com/openfisca
#
# This file is part of OpenFisca.
#
# OpenFisca is free software; you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# OpenFisca is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


"""
Convert OpenFisca Python source files containing simulation variables
to an OpenFisca ASG (abstract semantic graph)
using the RedBaron library.
"""


import argparse
import logging
import os
import pkg_resources
import sys

from openfisca_parsers import loading


log = logging.getLogger(__name__)


# Main function for script


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-p', '--country-package', default='openfisca_france')
    parser.add_argument('-v', '--verbose', action='store_true', default=False, help="Increase output verbosity")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING)

    country_package_dir = pkg_resources.get_distribution(args.country_package).location
    source_dir = os.path.join(country_package_dir, 'openfisca_france', 'model')
    redbaron_trees = loading.load(source_dir)

    return 0


if __name__ == "__main__":
    sys.exit(main())
