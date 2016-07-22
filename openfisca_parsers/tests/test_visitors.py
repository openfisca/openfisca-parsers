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


from nose.tools import assert_equal, assert_not_equal, assert_not_in
from redbaron import RedBaron

from openfisca_parsers import contexts, visitors
from openfisca_parsers.json_graph import show_json_graph


def test_legislation_at():
    source_code = '''\
class var1(Variable):
    column = FloatCol
    entity_class = Familles

    def function(self, simulation, period):
        P = simulation.legislation_at(period.start)
        return period, P
'''
    rbnode = RedBaron(source_code)[0]
    context = contexts.create()
    ofnode = visitors.visit_rbnode(rbnode, context)
    assert_equal(ofnode['formula']['type'], 'ParameterAtInstant')
    assert_equal(ofnode['formula']['parameter']['path'], [])


def test_legislation_at_with_path():
    source_code = '''\
class var1(Variable):
    column = FloatCol
    entity_class = Familles

    def function(self, simulation, period):
        P = simulation.legislation_at(period.start).aaa.bbb
        return period, P
'''
    rbnode = RedBaron(source_code)[0]
    context = contexts.create()
    ofnode = visitors.visit_rbnode(rbnode, context)
    assert_equal(ofnode['formula']['type'], 'ParameterAtInstant')
    assert_equal(ofnode['formula']['parameter']['path'], ['aaa', 'bbb'])


def test_legislation_at_with_path_later():
    source_code = '''\
class var1(Variable):
    column = FloatCol
    entity_class = Familles

    def function(self, simulation, period):
        P = simulation.legislation_at(period.start)
        return period, P.aaa.bbb
'''
    rbnode = RedBaron(source_code)[0]
    context = contexts.create()
    ofnode = visitors.visit_rbnode(rbnode, context)
    assert_equal(ofnode['formula']['type'], 'ParameterAtInstant')
    assert_equal(ofnode['formula']['parameter']['path'], ['aaa', 'bbb'])


def test_legislation_at_with_paths_forks():
    source_code = '''\
class var1(Variable):
    column = FloatCol
    entity_class = Familles

    def function(self, simulation, period):
        P = simulation.legislation_at(period.start).aaa.bbb
        xxx = P.xxx
        yyy = P.yyy
        zzz = yyy.zzz
        return period, xxx + zzz
'''
    rbnode = RedBaron(source_code)[0]
    context = contexts.create()
    ofnode = visitors.visit_rbnode(rbnode, context)
    assert_equal(ofnode['formula']['type'], 'ArithmeticOperation')
    left_ofnode, right_ofnode = ofnode['formula']['operands']
    assert_equal(left_ofnode['type'], 'ParameterAtInstant')
    assert_equal(right_ofnode['type'], 'ParameterAtInstant')
    assert_equal(left_ofnode['parameter']['type'], 'Parameter')
    assert_equal(right_ofnode['parameter']['type'], 'Parameter')
    assert_equal(left_ofnode['parameter']['path'], ['aaa', 'bbb', 'xxx'])
    assert_equal(right_ofnode['parameter']['path'], ['aaa', 'bbb', 'yyy', 'zzz'])
    assert_not_equal(left_ofnode, right_ofnode)


def test_period_this_year():
    source_code = '''\
class var1(Variable):
    column = FloatCol
    entity_class = Familles

    def function(self, simulation, period):
        period = period.this_year
        return period, 0
'''
    rbnode = RedBaron(source_code)[0]
    context = contexts.create()
    ofnode = visitors.visit_rbnode(rbnode, context)
    assert_equal(ofnode['formula']['type'], 'Constant')
    assert_equal(ofnode['formula']['value'], 0)
    assert_equal(ofnode['output_period']['type'], 'PeriodOperation')
    assert_equal(ofnode['output_period']['operator'], 'this_year')


def test_variable_class_without_formula():
    source_code = '''\
class rfr_n_1(Variable):
    column = IntCol
    entity_class = FoyersFiscaux
    label = u"Revenu fiscal de référence année n - 1"
'''
    rbnode = RedBaron(source_code)[0]
    context = contexts.create()
    ofnode = visitors.visit_rbnode(rbnode, context)
    assert_equal(ofnode['name'], 'rfr_n_1')
    assert_equal(ofnode['value_type'], 'int')
    assert_not_in('formula', ofnode)


def test_variable_class_with_period_size_independent_and_monetary_column():
    source_code = '''\
class nbptr_n_2(Variable):
    column = PeriodSizeIndependentIntCol(val_type = "monetary")
    entity_class = FoyersFiscaux
'''
    rbnode = RedBaron(source_code)[0]
    context = contexts.create()
    ofnode = visitors.visit_rbnode(rbnode, context)
    assert_equal(ofnode['name'], 'nbptr_n_2')
    assert_equal(ofnode['is_period_size_independent'], True)
    assert_equal(ofnode['value_type'], 'monetary')
    assert_not_in('formula', ofnode)


def test_variable_class_with_age_column():
    source_code = '''\
class age(Variable):
    column = AgeCol(val_type = "age")
    entity_class = Individus
    label = u"Âge (en années)"
'''
    rbnode = RedBaron(source_code)[0]
    context = contexts.create()
    ofnode = visitors.visit_rbnode(rbnode, context)
    assert_equal(ofnode['name'], 'age')
    assert_equal(ofnode['is_period_size_independent'], True)
    assert_equal(ofnode['value_type'], 'age')
    assert_not_in('formula', ofnode)


def test_variable_class_with_age_in_months_column():
    source_code = '''\
class age_en_mois(Variable):
    column = AgeCol(val_type = "months")
    entity_class = Individus
    label = u"Âge (en années)"
'''
    rbnode = RedBaron(source_code)[0]
    context = contexts.create()
    ofnode = visitors.visit_rbnode(rbnode, context)
    assert_equal(ofnode['name'], 'age_en_mois')
    assert_equal(ofnode['is_period_size_independent'], True)
    assert_equal(ofnode['value_type'], 'age_in_months')
    assert_not_in('formula', ofnode)


def test_variable_class_noop_with_formula():
    source_code = '''\
class var1(Variable):
    column = FloatCol
    entity_class = Familles

    def function(self, simulation, period):
        return period, 0
'''
    rbnode = RedBaron(source_code)[0]
    context = contexts.create()
    ofnode = visitors.visit_rbnode(rbnode, context)
    assert_equal(ofnode['name'], 'var1')
    assert_equal(ofnode['formula']['type'], 'Constant')
    assert_equal(ofnode['formula']['value'], 0)
    assert_equal(ofnode['output_period']['type'], 'Period')


def test_simulation_calculate():
    source_code = '''\
class var1(Variable):
    column = FloatCol
    entity_class = Familles

    def function(self, simulation, period):
        crds = simulation.calculate('crds', period)
        return period, crds
'''
    rbnode = RedBaron(source_code)[0]
    context = contexts.create()
    ofnode = visitors.visit_rbnode(rbnode, context)
    assert_equal(ofnode['formula']['type'], 'ValueForPeriod')
    assert_equal(ofnode['formula']['period']['type'], 'Period')
    assert_equal(ofnode['formula']['variable']['type'], 'Variable')
    assert_equal(ofnode['formula']['variable']['name'], 'crds')


def test_split_by_roles():
    source_code = '''\
class var1(Variable):
    column = FloatCol
    entity_class = Familles

    def function(self, simulation, period):
        crds_holder = simulation.compute('crds', period)
        crds = self.split_by_roles(crds_holder, roles = [VOUS, CONJ])
        return period, crds[VOUS]
'''
    rbnode = RedBaron(source_code)[0]
    context = contexts.create()
    ofnode = visitors.visit_rbnode(rbnode, context)
    assert_equal(ofnode['formula']['type'], 'ValueForRole')
    assert_equal(ofnode['formula']['variable']['type'], 'ValueForPeriod')
    assert_equal(ofnode['formula']['variable']['period']['type'], 'Period')
    assert_equal(ofnode['formula']['variable']['variable']['type'], 'Variable')
    assert_equal(ofnode['formula']['variable']['variable']['name'], 'crds')


def test_sum_by_entity():
    source_code = '''\
class var1(Variable):
    column = FloatCol
    entity_class = Familles

    def function(self, simulation, period):
        rag_holder = simulation.compute('rag', period)
        rag = self.sum_by_entity(rag_holder)
        return period, rag
'''
    rbnode = RedBaron(source_code)[0]
    context = contexts.create()
    ofnode = visitors.visit_rbnode(rbnode, context)
    assert_equal(ofnode['formula']['type'], 'ValueForEntity')
    assert_equal(ofnode['formula']['operator'], 'sum')
    assert_equal(ofnode['formula']['variable']['type'], 'ValueForPeriod')
    assert_equal(ofnode['formula']['variable']['variable']['type'], 'Variable')
    assert_equal(ofnode['formula']['variable']['variable']['name'], 'rag')


def test_cast_from_entity_to_role():
    source_code = '''\
class var1(Variable):
    column = FloatCol
    entity_class = Familles

    def function(self, simulation, period):
        taxe_habitation_holder = simulation.compute('taxe_habitation', period)
        taxe_habitation = self.cast_from_entity_to_role(taxe_habitation_holder, role = PREF)
        taxe_habitation = self.sum_by_entity(taxe_habitation)
        return period, taxe_habitation
'''
    rbnode = RedBaron(source_code)[0]
    context = contexts.create()
    ofnode = visitors.visit_rbnode(rbnode, context)
    assert_equal(ofnode['formula']['type'], 'ValueForEntity')
    assert_equal(ofnode['formula']['operator'], 'sum')
    assert_equal(ofnode['formula']['variable']['type'], 'ValueForRole')
    assert_equal(ofnode['formula']['variable']['role'], 'PREF')
    assert_equal(ofnode['formula']['variable']['variable']['type'], 'ValueForPeriod')
    assert_equal(ofnode['formula']['variable']['variable']['variable']['type'], 'Variable')
    assert_equal(ofnode['formula']['variable']['variable']['variable']['name'], 'taxe_habitation')


def test_reduce_nested_binary_operators_1():
    source_code = '1 + 2 + 3'
    rbnode = RedBaron(source_code)[0]
    context = contexts.create()
    ofnode = visitors.visit_rbnode(rbnode, context)
    assert_equal(ofnode['type'], 'ArithmeticOperation')
    assert_equal(ofnode['operator'], 'sum')
    assert_equal(len(ofnode['operands']), 3)
    assert all(operand_ofnode['type'] == 'Constant' for operand_ofnode in ofnode['operands']), ofnode['operands']


def test_reduce_nested_binary_operators_2():
    source_code = '1 + 2 + 3 + 4'
    rbnode = RedBaron(source_code)[0]
    context = contexts.create()
    ofnode = visitors.visit_rbnode(rbnode, context)
    assert_equal(ofnode['type'], 'ArithmeticOperation')
    assert_equal(ofnode['operator'], 'sum')
    assert_equal(len(ofnode['operands']), 4)
    assert all(operand_ofnode['type'] == 'Constant' for operand_ofnode in ofnode['operands']), ofnode['operands']


def test_reduce_nested_binary_operators_3():
    source_code = '(1 + 2) + (3 + 4)'
    rbnode = RedBaron(source_code)[0]
    context = contexts.create()
    ofnode = visitors.visit_rbnode(rbnode, context)
    assert_equal(ofnode['type'], 'ArithmeticOperation')
    assert_equal(ofnode['operator'], 'sum')
    assert_equal(len(ofnode['operands']), 4)
    assert all(operand_ofnode['type'] == 'Constant' for operand_ofnode in ofnode['operands']), ofnode['operands']


def test_reduce_nested_binary_operators_4():
    source_code = '1 + 2 - 3'
    rbnode = RedBaron(source_code)[0]
    context = contexts.create()
    ofnode = visitors.visit_rbnode(rbnode, context)
    assert_equal(ofnode['type'], 'ArithmeticOperation')
    assert_equal(ofnode['operator'], 'sum')
    assert_equal(len(ofnode['operands']), 3)
    assert_equal(ofnode['operands'][0]['type'], 'Constant')
    assert_equal(ofnode['operands'][1]['type'], 'Constant')
    assert_equal(ofnode['operands'][2]['type'], 'ArithmeticOperation')
    assert_equal(ofnode['operands'][2]['operator'], 'negate')


def test_reduce_nested_binary_operators_5():
    source_code = '1 - 2 - 3'
    rbnode = RedBaron(source_code)[0]
    context = contexts.create()
    ofnode = visitors.visit_rbnode(rbnode, context)
    assert_equal(ofnode['type'], 'ArithmeticOperation')
    assert_equal(ofnode['operator'], 'sum')
    assert_equal(len(ofnode['operands']), 2)
    assert_equal(ofnode['operands'][0]['type'], 'Constant')
    assert_equal(ofnode['operands'][1]['type'], 'ArithmeticOperation')
    assert_equal(ofnode['operands'][1]['operator'], 'negate')
    assert_equal(ofnode['operands'][1]['operand']['type'], 'ArithmeticOperation')
    assert_equal(ofnode['operands'][1]['operand']['operands'][0]['type'], 'Constant')
    assert_equal(ofnode['operands'][1]['operand']['operands'][1]['type'], 'ArithmeticOperation')
    assert_equal(ofnode['operands'][1]['operand']['operands'][1]['operator'], 'negate')
    assert_equal(ofnode['operands'][1]['operand']['operands'][1]['operand']['type'], 'Constant')


def test_reduce_nested_binary_operators_6():
    source_code = '1 * 2 * 3'
    rbnode = RedBaron(source_code)[0]
    context = contexts.create()
    ofnode = visitors.visit_rbnode(rbnode, context)
    assert_equal(ofnode['type'], 'ArithmeticOperation')
    assert_equal(ofnode['operator'], 'product')
    assert_equal(len(ofnode['operands']), 3)
    assert all(operand_ofnode['type'] == 'Constant' for operand_ofnode in ofnode['operands']), ofnode['operands']


def test_reduce_nested_binary_operators_7():
    source_code = '1 * 2 / 3'
    rbnode = RedBaron(source_code)[0]
    context = contexts.create()
    ofnode = visitors.visit_rbnode(rbnode, context)
    assert_equal(ofnode['type'], 'ArithmeticOperation')
    assert_equal(ofnode['operator'], 'product')
    assert_equal(len(ofnode['operands']), 2)
    assert_equal(ofnode['operands'][0]['type'], 'Constant')
    assert_equal(ofnode['operands'][1]['type'], 'ArithmeticOperation')
    assert_equal(ofnode['operands'][1]['operator'], '/')
