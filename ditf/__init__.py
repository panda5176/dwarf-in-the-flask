from flask import Flask, send_from_directory
from . import auth, blog, db


def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_json("config.json")

    db.init_app(app)

    app.register_blueprint(auth.bp)
    app.register_blueprint(blog.bp)
    app.add_url_rule("/", endpoint="index")

    return app


create_app()
