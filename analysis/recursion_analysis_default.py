import os
import pandas as pd
import numpy as np
import json
# import matplotlib.pyplot as plt

from sklearn import svm, linear_model, discriminant_analysis, neighbors
from sklearn import tree, naive_bayes, ensemble, neural_network, gaussian_process
from sklearn.model_selection import cross_validate, KFold, train_test_split
from sklearn import metrics
from sklearn import preprocessing

from scipy.io import arff as arff_io
from pymfe.mfe import MFE

from imblearn.over_sampling import SMOTE
from imblearn.under_sampling import RandomUnderSampler

from NoiseFiltersPy.HARF import HARF
from NoiseFiltersPy.ENN import ENN

import constants
from config import config
from Default import Default
from Random import Random
from meta_db.db.DBHelper import DBHelper

from R_Model import *
# Importing utils from R
from rpy2.robjects.packages import importr
import rpy2.robjects.packages as rpackages
from rpy2.robjects.vectors import StrVector
from rpy2.robjects.packages import SignatureTranslatedAnonymousPackage

# For Formulae
from rpy2.robjects import IntVector, Formula

# For Pandas
import rpy2.robjects as ro
from rpy2.robjects import pandas2ri
from rpy2.robjects import numpy2ri
from rpy2.robjects.conversion import localconverter

# Getting R functions
utils = importr("utils")
utils.chooseCRANmirror(ind=1)

# Geting packages
packages = ("reshape2", "e1071", "kknn", "randomForest", "C50", "rpart", "neuralnet")
to_install = [pack for pack in packages if not rpackages.isinstalled(pack)]
if to_install:
    utils.install_packages(StrVector(to_install))

e1071 = importr("e1071")
kknn = importr("kknn")
randomForest = importr("randomForest")
c50 = importr("C50")
rpart = importr("rpart")
neuralnet = importr("neuralnet")

RANDOM_STATE = 73
np.random.seed(RANDOM_STATE)

SCORE = "balanced_accuracy_mean"
SCORE_RAW = "balanced_accuracy"

grey_palette = ['rgb(208, 209, 211)',
                'rgb(185, 191, 193)',
                'rgb(137, 149, 147)',
                'rgb(44, 54, 60)',
                'rgb(3, 3, 3)'
               ]

pprocs = {
    "RandomUnder": RandomUnderSampler(random_state = RANDOM_STATE).fit_resample,
    "SMOTE": SMOTE(random_state = RANDOM_STATE).fit_resample,
    "HARF": HARF(seed = RANDOM_STATE),
    "ENN": ENN()
}
def preprocessor(name, values, target):
    if name in ["RandomUnder", "SMOTE"]:
        return pprocs[name](values, target)
    else:
        filter = pprocs[name](values, target)
        return (filter.cleanData, filter.cleanClasses)

def real_scores(values, target):
    clf_models = {}
    svm_clf = svm.SVC(gamma = "auto").fit(values, target )
    clf_models["svm"] = svm_clf # Actually not needed, the cv does the training again
    lg_clf = linear_model.LogisticRegression(random_state = RANDOM_STATE, solver = 'lbfgs').fit(values, target )
    clf_models["logistic_regression"] = lg_clf
    lineardisc_clf = discriminant_analysis.LinearDiscriminantAnalysis().fit(values, target )
    clf_models["linear_discriminant"] = lineardisc_clf
    neigh_clf = neighbors.KNeighborsClassifier().fit(values, target)
    clf_models["kneighbors"] = neigh_clf
    dectree_clf = tree.DecisionTreeClassifier(random_state = RANDOM_STATE).fit(values, target )
    clf_models["decision_tree"] = dectree_clf
    gaussian_clf = naive_bayes.GaussianNB().fit(values, target )
    clf_models["gaussian_nb"] = gaussian_clf
    random_forest_clf = ensemble.RandomForestClassifier(n_estimators = 100).fit(values, target )
    clf_models["random_forest"] = random_forest_clf
    gradient_boost_clf = ensemble.GradientBoostingClassifier().fit(values, target )
    clf_models["gradient_boosting"] = gradient_boost_clf
    results = {}
    for clf in clf_models.keys():
        cv_results = cross_validate(clf_models[clf], values, target, cv = 10, scoring = SCORE_RAW)
        results["None+{}".format(clf)] = np.mean(cv_results["test_score"])

    for pproc in pprocs.keys():
        try:
            new_values, new_target = preprocessor(pproc, values, target)
        except:
            for clf in clf_models.keys():
                results["{}+{}".format(pproc, clf)] = 0
            continue

        for clf in clf_models.keys():
            try:
                cv_results = cross_validate(clf_models[clf], new_values, new_target, cv = 10, scoring = SCORE_RAW)
            except ValueError:
                cv_results = cross_validate(clf_models[clf], values, target, cv = 10, scoring = SCORE_RAW)
            results["{}+{}".format(pproc, clf)] = np.mean(cv_results["test_score"])
    return results

translator = {
    "gaussian_nb": "GNB",
    "random_forest": "RF",
    "randomForest": "RF",
    "random": "Random",
    "default": "Default"
}

db = DBHelper()
mfe = MFE()
le = preprocessing.LabelEncoder()


def deal_dataset(name):
    data = arff_io.loadarff(config["dataset"]["folder"] + name + ".arff")
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
    return values, target

def calculate_metafeature(name, values, target):
    mfe.fit(values, target)
    try:
        ft = mfe.extract(supress_warnings = True)
    except AttributeError:
        mfe.fit(values.astype(float), target)
        ft = mfe.extract(supress_warnings = True)
    labels = np.array(ft[0])
    results = np.array(ft[1])
    nan_columns = np.isnan(results)
    not_nan = np.invert(nan_columns)
    # Adding name to the list
    labels = ["name"] + labels[not_nan].tolist()
    results = [name] + results[not_nan].tolist()
    for indx, result in enumerate(results):
        if isinstance(result, complex):
            results[indx] = result.real
    cols =  []
    for type in labels:
        if type == "int":
            type = "intt"
        cols.append(type.replace(".", "_"))
    results = np.array(results).reshape((1, len(results)))
    results = pd.DataFrame(results, columns = cols)
    return results

metadata = pd.DataFrame(db.get_all_metadata(), columns = db.metadata_columns()).drop("id", axis = 1)
models = pd.DataFrame(db.get_all_models(), columns = db.models_columns()).drop("id", axis = 1)
combinations = pd.DataFrame(db.get_all_combinations(), columns = db.combinations_columns())
preperformance = pd.DataFrame(db.get_all_preperformance(), columns = db.preperformance_columns()).drop("id", axis = 1)
# Not null preperformance
preperformance = preperformance[~preperformance.isnull().any(axis = 1)]
preperformance = pd.merge(preperformance, combinations, left_on = "combination_id", right_on = "id").drop(["combination_id", "id", "num_preprocesses"], axis = 1)

models = models.rename(columns = {"model": "classifier"})
models["preprocesses"] = "None"
scores = pd.concat([models, preperformance], sort = False)
scores = scores[scores.classifier != "neural_network"]
models = models[models.classifier != "neural_network"]

metadata_means = {feature: np.mean(metadata[feature]) for feature in metadata.columns if feature != "name"}
metadata.fillna(value = metadata_means, inplace = True)

data = pd.merge(metadata, scores, on = "name")
data = data[data.preprocesses.isin(constants.PRE_PROCESSES + ["None"]) & data.classifier.isin(constants.CLASSIFIERS)]

meta_means = {feature: np.mean(metadata[feature]) for feature in metadata.columns if feature != "name"}

if not os.path.exists("analysis/plots"):
    os.makedirs("analysis/plots")
if not os.path.exists("analysis/plots/base_analysis"):
    os.makedirs("analysis/plots/base_analysis")

mean_scores = []
std_scores = []
for score in constants.CLASSIFIERS_SCORES:
    mean_scores.append(score + "_mean")
    std_scores.append(score + "_std")

reg_models = {}
reg_models["ann"] = lambda: R_Model(neuralnet.neuralnet)
reg_models["cart"] = lambda: R_Model(rpart.rpart)
reg_models["randomForest"] = lambda: R_Model(randomForest.randomForest)
reg_models["svm"] = lambda: SVR()
reg_models["dwnn"] = lambda: KNN()
reg_models["random"] = lambda: Random(random_seed = RANDOM_STATE)
reg_models["default"] = lambda: Default()

# Function to get only datasets with all results (combinations)
def filter_dataset(database):
    datasets_filtered = []
    for dataset in database.name.unique():
        split = database[database.name == dataset]
        keep = True
        for clf in constants.CLASSIFIERS:
            for pp in constants.PRE_PROCESSES + ['None']:
                if len(split[(split.classifier == clf) & (split.preprocesses == pp)]) < 1:
                    keep = False
        if keep:
            datasets_filtered.append(dataset)
    return datasets_filtered

datasets = pd.Series(filter_dataset(data))

results = {}

results["pp_wins"] = {}
results["clf_wins"] = {}
results["wins"] = {}

num_datasets = {}

TURNS = 5

regressor_type = "default"
results["pp_wins"][regressor_type] = [0] * TURNS
results["clf_wins"][regressor_type] = [0] * TURNS
results["wins"][regressor_type] = [0] * TURNS

num_datasets[regressor_type] = [0] * TURNS

train_dt, test_dt = train_test_split(datasets, test_size = 0.1, random_state = RANDOM_STATE, shuffle = True)
targets = data[data.name.isin(train_dt)]
trained_reg = {}

for clf in constants.CLASSIFIERS:
    for preprocess in (constants.PRE_PROCESSES + ['None']):
        trained_reg["{}+{}".format(preprocess, clf)] = reg_models[regressor_type]()
        target = targets.query("classifier == '{}' and preprocesses == '{}'".format(clf, preprocess))
        meta_target = target.drop(["name", "classifier", "preprocesses", *mean_scores, *std_scores], axis = 1)
        label_target = target[SCORE].values
        trained_reg["{}+{}".format(preprocess, clf)].fit(meta_target, label_target)

tests = data[data.name.isin(test_dt)]
for test_dataset in tests.name.unique():
    print(test_dataset)
    dt_values, dt_target = deal_dataset(test_dataset)

    dataset_info = tests[tests.name == test_dataset]
    meta_data = dataset_info.drop(
            ["name", "classifier", "preprocesses", *mean_scores, *std_scores],
            axis = 1
        ).iloc[[0]]

    for turn in range(TURNS):
        num_datasets[regressor_type][turn] += 1
        print("MAKING TURNS")
        reg_results = {}
        for model in trained_reg:
            reg_results[model] = trained_reg[model].predict(meta_data)
        max_predicted = max(reg_results.keys(), key = (lambda key: reg_results[key]))
        pp_pred, clf_pred = max_predicted.split("+")
        if turn == 0:
            print("TURN 0")
            true_max = dataset_info[dataset_info[SCORE] == dataset_info[SCORE].max()]
            pp_maxes = [entry.preprocesses for indx, entry in true_max.iterrows()]
            clf_maxes = [entry.classifier for indx, entry in true_max.iterrows()]
            score_pred = dataset_info[(dataset_info.preprocesses == pp_pred) & (dataset_info.classifier == clf_pred)][SCORE]
            results["wins"][regressor_type][turn] += 1 if ((pp_pred in pp_maxes) and (clf_pred in clf_maxes)) else 0
        else:
            print("RECURSION TURN")
            true_max = max(clf_scores, key = (lambda pp_clf: clf_scores[pp_clf]))
            max_comb_value = clf_scores[true_max]
            true_maxes = [comb for comb in clf_scores if clf_scores[comb] == max_comb_value]
            pp_maxes = []; clf_maxes = []
            for max_v in true_maxes:
                pp, clf = max_v.split("+")
                pp_maxes.append(pp); clf_maxes.append(clf)
            results["wins"][regressor_type][turn] += 1 if (max_predicted in true_maxes) else 0

        results["pp_wins"][regressor_type][turn] += 1 if (pp_pred in pp_maxes) else 0
        results["clf_wins"][regressor_type][turn] += 1 if (clf_pred in clf_maxes) else 0

        if (pp_pred == "None") or not (pp_pred in pp_maxes):
            print("END PP")
            break
        else:
            try:
                dt_values, dt_target = preprocessor(pp_pred, dt_values, dt_target)
                meta_data = calculate_metafeature(test_dataset, dt_values, dt_target)
            except:
                break
            print("HERE!")
            meta_results = {}
            for indx, col in enumerate(dataset_info.columns.drop(["name", "classifier", "preprocesses", *mean_scores, *std_scores])):
                if col not in meta_data.columns:
                    meta_results[col] = meta_means[col]
                else:
                    meta_results[col] = float(meta_data[col])
            meta_data = pd.DataFrame.from_dict([meta_results])
            clf_scores = real_scores(dt_values, dt_target)
        print("END TURN")
    print("END END")

print(results)
print(num_datasets)
with open("analysis/plots/recursion/" + SCORE + ".df.{}.json".format(RANDOM_STATE), "w") as fd:
    json.dump(results, fd, indent = 4)
with open("analysis/plots/recursion/" + SCORE + "__numdatasets.df.{}.json".format(RANDOM_STATE), "w") as fd:
    json.dump(num_datasets, fd, indent = 4)
