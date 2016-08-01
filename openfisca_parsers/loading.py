# openfisca-france model loading

import os
from redbaron import RedBaron


def load():
    source_dir = '../../openfisca-france/openfisca_france/model/'
    filenames = []

    for root, directories, files in os.walk(source_dir):
        for filename in files:
            complete_filename = os.path.join(root, filename)
            assert complete_filename[:len(source_dir)] == source_dir
            complete_filename = complete_filename[len(source_dir):]
            filenames.append(complete_filename)

    filenames.remove('base.py')
    filenames.remove('datatrees.py')
    filenames.remove('prelevements_obligatoires/prelevements_sociaux/cotisations_sociales/preprocessing.py')

    redbaron_trees = {}
    for filename in filenames:
        with open(source_dir + filename) as source_file:
            source_code = source_file.read()
        red = RedBaron(source_code)
        redbaron_trees[filename] = red
        # print('{} parsed'.format(filename))

    return redbaron_trees
