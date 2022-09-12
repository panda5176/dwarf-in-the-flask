from datetime import datetime, timezone
from os.path import join as path_join
from xml.etree.ElementTree import Element, ElementTree, SubElement, indent

from flask import Flask, render_template, send_file
from flask_wtf.csrf import CSRFError, CSRFProtect
from . import admin, auth, blog, db


def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_json("config.json")

    db.init_app(app)

    app.register_blueprint(admin.BP)
    app.register_blueprint(auth.BP)
    app.register_blueprint(blog.BP)
    app.add_url_rule("/", endpoint="index")

    csrf = CSRFProtect()
    csrf.init_app(app)

    @app.errorhandler(CSRFError)
    @app.errorhandler(403)
    def handle_error_403(error):
        return (
            render_template(
                "error.html",
                error_code=error.code,
                error_type=error.name,
                error_desc="접근이 거부되었습니다.",
            ),
            error.code,
        )

    @app.errorhandler(404)
    def handle_error_404(error):
        return (
            render_template(
                "error.html",
                error_code=error.code,
                error_type=error.name,
                error_desc="페이지를 찾을 수 없습니다.",
            ),
            error.code,
        )

    @app.route("/sitemap.xml", methods=("GET",))
    def show_sitemap():
        cur = db.get_cur()
        cur.execute("SELECT id, created, modified FROM posts ORDER BY created;")
        posts = cur.fetchall()

        xml_urlset = Element("urlset")
        xml_urlset.attrib = {
            "xmlns": "http://www.sitemaps.org/schemas/sitemap/0.9"
        }

        # index
        xml_url = SubElement(xml_urlset, "url")
        xml_loc = app.config["DOMAIN"]
        xml_lastmod = (
            datetime.now()
            .replace(microsecond=0, tzinfo=timezone.utc)
            .isoformat()
        )
        SubElement(xml_url, "loc").text = xml_loc
        SubElement(xml_url, "lastmod").text = xml_lastmod
        SubElement(xml_url, "changefreq").text = "daily"
        SubElement(xml_url, "priority").text = "0.8"

        # posts
        for post in posts:
            xml_url = SubElement(xml_urlset, "url")
            xml_loc = f"{app.config['DOMAIN']}{post['id']}"
            xml_lastmod = (
                post["modified"]
                .replace(microsecond=0, tzinfo=timezone.utc)
                .isoformat()
            )
            SubElement(xml_url, "loc").text = xml_loc
            SubElement(xml_url, "lastmod").text = xml_lastmod
            SubElement(xml_url, "changefreq").text = "daily"
            SubElement(xml_url, "priority").text = "0.5"

        xml_tree = ElementTree(xml_urlset)
        indent(xml_tree)

        xml_path = path_join(app.static_folder, "sitemap.xml")
        xml_tree.write(xml_path, encoding="utf-8", xml_declaration=True)

        return send_file(xml_path)

    @app.route("/robots.txt", methods=("GET",))
    def show_robots():
        return send_file(path_join(app.static_folder, "robots.txt"))

    return app


create_app()
