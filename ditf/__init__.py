from datetime import timezone
from os.path import join as path_join
from xml.etree.ElementTree import Element, ElementTree, SubElement, indent

from flask import Flask, send_file
from . import auth, blog, db


def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_json("config.json")

    db.init_app(app)

    app.register_blueprint(auth.bp)
    app.register_blueprint(blog.bp)
    app.add_url_rule("/", endpoint="index")

    @app.route("/sitemap.xml", methods=("GET",))
    def show_sitemap():
        cur = db.get_cur()
        cur.execute("SELECT id, created, modified FROM posts ORDER BY created;")
        posts = cur.fetchall()

        xml_urlset = Element("urlset")
        xml_urlset.attrib = {
            "xmlns": "http://www.sitemaps.org/schemas/sitemap/0.9"
        }
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
