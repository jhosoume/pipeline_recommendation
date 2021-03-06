import sys
import mysql
from os import listdir
from os.path import isfile, join
import pandas as pd
import numpy as np

from sklearn import svm, linear_model, discriminant_analysis, neighbors
from sklearn import tree, naive_bayes, ensemble, neural_network
from sklearn.model_selection import cross_validate
from sklearn.metrics import SCORERS
from sklearn import preprocessing
from scipy.io import arff as arff_io

from imblearn.over_sampling import SMOTE
from imblearn.over_sampling import ADASYN

from NoiseFiltersPy.HARF import HARF
from NoiseFiltersPy.AENN import AENN

import constants
from config import config

from pre_processing import model_generation
from meta_db.db.DBHelper import DBHelper


np.random.seed(constants.RANDOM_STATE)

PRE_PROCESSES = {"imbalance": { "SMOTE": SMOTE(random_state = constants.RANDOM_STATE),
                                "ADASYN": ADASYN(random_state = constants.RANDOM_STATE),
                              },
                 "noise_filter": { "HARF": HARF(seed = constants.RANDOM_STATE),
                                   "AENN": AENN()
                                 },
                 }

datasets = [f for f in listdir(config["dataset"]["folder"])
                if ( isfile(join(config["dataset"]["folder"], f)) and
                   ( f.endswith("json") or f.endswith("arff") ) )]

db = DBHelper()
le = preprocessing.LabelEncoder()
for dataset in datasets:
    name = dataset[:-5]
    print("[{}]".format(name))
    if dataset.endswith("json"):
        data = pd.read_json(config["dataset"]["folder"] + dataset)
    elif dataset.endswith("arff"):
        data = arff_io.loadarff(config["dataset"]["folder"] + dataset)
        data = pd.DataFrame(data[0])
    target = data["class"].values
    if target.dtype == np.object:
        le.fit(target)
        target = le.transform(target)
    values = data.drop("class", axis = 1)
    # Check if any is a string, some classifiers only deals with numeric data
    for dtype, key in zip(values.dtypes, values.keys()):
        if dtype == np.object:
            le.fit(values[key].values)
            values[key] = le.transform(values[key].values)
    values = values.values
    for type in PRE_PROCESSES:
        for preproc_name in PRE_PROCESSES[type]:
            model_generation.calculate(name, values, target, PRE_PROCESSES[type][preproc_name], preproc_name, type)
