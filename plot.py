import matplotlib.pyplot as plt
import numpy as np
import Input
from pathlib import Path
import json

class Settings:

    def __init__(self):
        self.equation_names = None
        self.gridm = 4
        self.figsize = (9,6)
        self.ylabel = "y"
        self.xlabel = "time"
        self.number_of_eq = None


def create_subplots(t, y, settings):
    m =  settings.gridm #number of diagramms in one line
    d = settings.number_of_eq
    n = -(-d // m)   # 3
    if d < m:
        m = d
    names = settings.equation_names
    if names == None:
        names = [f"variable {i+1}" for i in range(d)]

    fig, axs = plt.subplots(n, m, figsize=settings.figsize, squeeze=False)
    counter = 0
    for i in range(n):
        for j in range(m):
            if counter < d:
                axs[i,j].plot(t, y[counter], label = names[counter])
                axs[i,j].set_xlabel(settings.xlabel)
                axs[i,j].set_ylabel(settings.ylabel)
                axs[i,j].legend()
                counter+=1
            else:
                axs[i,j].axis("off")

    fig.tight_layout(h_pad=3, w_pad=2.5)
    return fig

def main_plot(cvs_name, json_name):
    file_name_csv = "".join(cvs_name.split())
    if not file_name_csv.lower().endswith(".csv"):
            file_name_csv += ".csv"
    path_csv = Path("solutions") / Path(file_name_csv).expanduser()
    t, *ys = np.loadtxt(path_csv, delimiter=",", skiprows=1, unpack=True)
    file_name_json = "".join(json_name.split())
    path_json = Input.parse_input_path(file_name_json, "Models")
    data_json = json.loads(path_json.read_text())
    #set the settings 
    settings = Settings() #neccesary so the class is known
    settings.number_of_eq = len(ys)
    names = data_json.get("names", {})
    settings.equation_names = [names.get(f"y{i}", f"equation {i}") for i in range(1, len(ys) + 1)]
    fig = create_subplots(t,ys,settings)
    plt.show()
    pass

#main_plot("oo.csv", "ivp.json")
