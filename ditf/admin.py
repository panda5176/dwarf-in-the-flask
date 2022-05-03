from flask import (
    Blueprint,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_paginate import Pagination, get_page_args
from werkzeug.exceptions import abort

from .auth import admin_only, get_user
from .db import get_conn, get_cur

BP = Blueprint("admin", __name__, url_prefix="/admin")


@BP.route("/", methods=("GET",))
@admin_only
def users():
    per_page = 20
    page, _, offset = get_page_args(per_page=per_page)

    cur = get_cur()
    cur.execute("SELECT COUNT(*) FROM users;")
    total = cur.fetchone()[0]

    cur.execute(
        "SELECT id, username, mail FROM users ORDER BY id "
        "DESC LIMIT %s OFFSET %s;",
        (per_page, offset),
    )
    users = cur.fetchall()

    return render_template(
        "admin/users.html",
        users=users,
        total=total,
        pagination=Pagination(
            page=page,
            total=total,
            per_page=per_page,
            prev_label="<<",
            next_label=">>",
            format_total=True,
            format_number=True,
        ),
        search=True,
        bs_version=5,
    )


@BP.route("/<int:id>/delete", methods=("POST",))
@admin_only
def delete_user(id):
    conn = get_conn()
    cur = get_cur()
    cur.execute("DELETE FROM users WHERE id = %s;", (id,))
    conn.commit()
    flash("The user was successfully deleted.", "info")

    return redirect(url_for("admin.users"))

