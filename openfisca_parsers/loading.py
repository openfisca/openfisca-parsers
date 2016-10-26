# -*- coding: utf-8 -*-

# openfisca-france model loading

import os
from redbaron import RedBaron


def load(source_dir):
    if not source_dir.endswith('/'):
        source_dir += '/'

    filenames = []
    blacklist = [
        'base.py',
        'datatrees.py',
        'prelevements_obligatoires/prelevements_sociaux/cotisations_sociales/preprocessing.py',
        ]

    for root, directories, files in os.walk(source_dir):
        for filename in files:
            if filename.endswith('.py') and filename not in blacklist:
                complete_filename = os.path.join(root, filename)
                assert complete_filename[:len(source_dir)] == source_dir
                complete_filename = complete_filename[len(source_dir):]
                filenames.append(complete_filename)

    redbaron_trees = {}
    for filename in filenames:
        with open(source_dir + filename) as source_file:
            source_code = source_file.read()
        red = RedBaron(source_code)
        redbaron_trees[filename] = red
        print(u'{} parsed'.format(filename).encode('utf-8'))

    return redbaron_trees
