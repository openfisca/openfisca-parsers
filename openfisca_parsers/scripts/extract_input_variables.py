#! /usr/bin/env python
# -*- coding: utf-8 -*-


# OpenFisca -- A versatile microsimulation software
# By: OpenFisca Team <contact@openfisca.fr>
#
# Copyright (C) 2011, 2012, 2013, 2014, 2015 OpenFisca Team
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


"""Extract input variables from Python formulas using lib2to3."""


import argparse
import importlib
import logging
import os
import sys

from openfisca_parsers import input_variables_extractors


app_name = os.path.splitext(os.path.basename(__file__))[0]
log = logging.getLogger(app_name)


def main():
    parser = argparse.ArgumentParser(description = __doc__)
    parser.add_argument('-c', '--country-package', default = 'openfisca_france',
        help = u'name of the OpenFisca package to use for country-specific variables & formulas')
    parser.add_argument('-n', '--name', default = None,
        help = u'name of the formula to extract variables from (default: all)')
    parser.add_argument('-v', '--verbose', action = 'store_true', default = False, help = "increase output verbosity")
    args = parser.parse_args()
    logging.basicConfig(level = logging.DEBUG if args.verbose else logging.WARNING, stream = sys.stdout)

    country_package = importlib.import_module(args.country_package)
    TaxBenefitSystem = country_package.init_country()
    tax_benefit_system = TaxBenefitSystem()

    extractor = input_variables_extractors.setup(tax_benefit_system)

    if args.name is None:
        for column in tax_benefit_system.column_by_name.itervalues():
            print column.name
            input_variables, parameters = extractor.get_input_variables_and_parameters(column)
            if input_variables is not None:
                print u' Input variables:', u', '.join(sorted(input_variables))
            if parameters:
                print u' Parameters:', u', '.join(sorted(parameters))
    else:
        column = tax_benefit_system.column_by_name[args.name]
        print column.name
        input_variables, parameters = extractor.get_input_variables_and_parameters(column)
        if input_variables is not None:
            print u' Input variables:', u', '.join(sorted(input_variables))
        if parameters:
            print u' Parameters:', u', '.join(sorted(parameters))

    return 0


if __name__ == "__main__":
    sys.exit(main())
