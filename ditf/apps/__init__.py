import dash_core_components as dcc
import dash_html_components as html
from dash import Dash
from flask import Blueprint, current_app, render_template

BP = Blueprint("apps", __name__, url_prefix="/apps")


@BP.route("/", methods=("GET",))
def iris():
    import plotly.express as px

    current_app.config["dash"]["iris"]["scatter"].layout = html.Div(
        children=[
            html.H1(children="Iris Scatter"),
            dcc.Graph(
                id="iris-scatter",
                figure=px.scatter(
                    px.data.iris(),
                    x="sepal_width",
                    y="sepal_length",
                    color="species",
                ),
            ),
        ]
    )
    current_app.config["dash"]["iris"]["box"].layout = html.Div(
        children=[
            html.H1(children="Iris Box"),
            dcc.Graph(
                id="iris-box", figure=px.box(px.data.iris(), y="sepal_length"),
            ),
        ]
    )
    return render_template("apps/iris.html")


def init_dash(server):
    dash_apps = dict()

    dash_apps["iris"] = dict()
    iris_scatter = Dash(server=server, routes_pathname_prefix="/iris-scatter/")
    iris_scatter.layout = html.Div()
    dash_apps["iris"]["scatter"] = iris_scatter
    iris_box = Dash(server=server, routes_pathname_prefix="/iris-box/")
    iris_box.layout = html.Div()
    dash_apps["iris"]["box"] = iris_box

    return dash_apps

