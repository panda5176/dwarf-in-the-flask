import click
from flask import current_app, g
from flask.cli import with_appcontext
import psycopg2, psycopg2.extras


def get_conn():
    if "conn" not in g:
        db_config = current_app.config["DATABASE"]
        g.conn = psycopg2.connect(
            host=db_config["HOST"],
            user=db_config["USER"],
            password=db_config["PASSWORD"],
            port=db_config["PORT"],
        )

    return g.conn


def get_cur():
    if "cur" not in g:
        g.cur = get_conn().cursor(cursor_factory=psycopg2.extras.DictCursor)

    return g.cur


def close_cur(e=None):
    cur = g.pop("cur", None)

    if cur is not None:
        cur.close()


def close_conn(e=None):
    close_cur()
    conn = g.pop("conn", None)

    if conn is not None:
        conn.close()


def init_db():
    conn = get_conn()
    cur = get_cur()

    with current_app.open_resource("schema.sql") as sql_fh:
        cur.execute(sql_fh.read().decode("utf8"))
        conn.commit()


@click.command("init-db")
@with_appcontext
def init_db_command():
    """Clear the existing data and create new tables."""
    init_db()
    click.echo("Initialized the database.")


def init_app(app):
    app.teardown_appcontext(close_conn)
    app.cli.add_command(init_db_command)
