import os
import pandas as pd
from scipy import stats
import numpy as np
import json

import plotly.io as pio
import plotly.express as px
import plotly.graph_objects as go

REP = "reduced_30"

SCORE = "balanced_accuracy_mean"
DIST_FUNCTION = stats.sem
# DIST_FUNCTION = lambda d: np.mean(np.abs( d - np.mean(d) ))

pio.templates.default = "plotly_white"


grey_palette = ['rgb(208, 209, 211)',
                'rgb(137, 149, 147)',
               ]

translator = {
    "svm": "SVM",
    "logistic_regression": "LG",
    "linear_discriminant": "LD",
    "kneighbors": "kNN",
    "decision_tree": "DT",
    "gaussian_nb": "GNB",
    "random_forest": "RF",
    "gradient_boosting": "GB",
    "neural_network": "NN",
    "knn": "kNN",
    "Svm": "SVM",
    "random": "Random",
    "default": "Default"
}


with open("analysis/plots/base_analysis/{}_normalized_rep_{}.json".format(SCORE, REP), "r") as fd:
    all_results = json.load(fd)

results = { baseline:{
                reg:{ measure: 0 for measure in ["mean", "dist"]}
                for reg in all_results[0]["random"].keys()}
            for baseline in all_results[0].keys()
           }

for baseline in results.keys():
    for reg in results[baseline].keys():
        results[baseline][reg]["mean"] = np.mean([res[baseline][reg] for res in all_results])
        results[baseline][reg]["dist"] = DIST_FUNCTION([res[baseline][reg] for res in all_results])

data_plot = []
for indx, baseline in enumerate(results.keys()):
    bar = go.Bar(
        name = translator[baseline],
        x = list(map(lambda reg: translator[reg], results[baseline].keys())),
        y = [results[baseline][reg]["mean"] for reg in results[baseline].keys()],
        error_y = dict(
            type = "data",
            array = [results[baseline][reg]["dist"] for reg in results[baseline].keys()]),
        marker_color = grey_palette[indx],
    )
    data_plot.append(bar)

    # bar = go.Bar(
    #     name = translator[baseline],
    #     x = list(map(lambda reg: translator[reg], non_normalized_results[baseline].keys())),
    #     y = list([np.sum(values) for values in non_normalized_results.values()]),
    #     marker_color = grey_palette[1]
    # )

fig = go.Figure(data = data_plot)

fig.update_layout(barmode = 'group')
fig.update_layout(
    xaxis_title = "Regressor",
    yaxis_title = "Gain (%) ",
    uniformtext_minsize = 16,
    font = dict(
        size = 16,
    ),
    yaxis_title_standoff = 0    ,

)

fig.update_yaxes(
    showgrid = True,
    linewidth = 1,
    linecolor = "black",
    ticks = "inside",
    mirror = True,
    range = [-80, 100],
    tickfont= dict(
        size= 16,
        color = 'black'
    ),
    titlefont = dict(
        size = 18
    )
)

fig.update_xaxes(
    showgrid = True,
    linewidth = 1,
    linecolor = "black",
    ticks = "inside",
    tickson = "boundaries",
    mirror = True,
    tickfont= dict(
        size= 16,
        color = 'black'
    ),
    titlefont = dict(
        size = 18
    ),

)

fig.update_yaxes(
    zeroline = True,
    zerolinewidth = 2,
    zerolinecolor = "black",
)

fig.update_layout(legend_orientation="h")
fig.update_layout(
    legend = dict(
                   x = 0.25,
                   y = 1.11,
                   traceorder= "normal",
                   # bordercolor= "Black",
                   # borderwidth= 0.5
    )
)

# fig.update_layout(legend_orientation="h")
# fig.update_layout(
#     legend = dict(
#                    x = 0,
#                    y = 1.1,
#                    traceorder= "normal",
#                    # bordercolor= "Black",
#                    # borderwidth= 0.5
#     )
# )
fig.write_image("analysis/plots/base_analysis/" + SCORE + "_rep_normalized.eps")
fig.write_image("analysis/plots/base_analysis/" + SCORE + "_rep_normalized.png")
fig.write_image("/home/jhosoume/unb/tcc/ICDM/img/base_level_analysis/" + baseline  + "_" + SCORE + "_rep_normalized.eps")
fig.write_image("/home/jhosoume/unb/tcc/ICDM/img/base_level_analysis/" + baseline + "_" + SCORE + "_rep_normalized.png")
