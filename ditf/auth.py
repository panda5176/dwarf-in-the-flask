import functools, re

from flask import (
    Blueprint,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_paginate import Pagination, get_page_args
from markdown import markdown
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_conn, get_cur

bp = Blueprint("auth", __name__, url_prefix="/auth")


def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for("auth.login"))

        return view(**kwargs)

    return wrapped_view


def admin_only(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user["id"] != 1:
            flash("Invalid access.", "warning")
            return redirect(url_for("blog.index"))

        return view(**kwargs)

    return wrapped_view


@bp.route("/register", methods=("GET", "POST"))
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        password_confirm = request.form["password-confirm"]
        mail = request.form["mail"]
        error = None

        if not username:
            error = "Username is required."
        elif not password:
            error = "Password is required."
        elif not password_confirm:
            error = "Password confirmation is required."
        elif password != password_confirm:
            error = "Confirm password."
        elif not mail:
            error = "Mail address is required."
        elif re.match("[^\w]", username):
            error = "Username with only alphabets, numbers and underscores."
        elif re.match("[^\w]", password):
            error = "Password with only alphabets, numbers and underscores."

        if error:
            flash(error, "warning")
        else:
            conn = get_conn()
            cur = get_cur()
            cur.execute(
                "SELECT username FROM users WHERE username = %s;", (username,)
            )
            if cur.fetchone():
                flash(f"User {username} is already registered.", "warning")
            else:
                cur.execute("SELECT mail FROM users WHERE mail = %s;", (mail,))

                if cur.fetchone():
                    flash(f"Mail {mail} is already registered.", "warning")
                else:
                    cur.execute(
                        "INSERT INTO users (username, password, mail) "
                        "VALUES (%s, %s, %s);",
                        (username, generate_password_hash(password), mail),
                    )
                    conn.commit()
                    flash("Successfully registered.", "info")
                    return redirect(url_for("auth.login"))

    return render_template("auth/register.html")


@bp.route("/login", methods=("GET", "POST"))
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        error = None

        if re.match("[^\w]", username):
            error = "Username with only alphabets, numbers and underscores."
        elif re.match("[^\w]", password):
            error = "Password with only alphabets, numbers and underscores."

        if error:
            flash(error, "warning")
        else:
            cur = get_cur()
            cur.execute(
                "SELECT id, username, password, mail, about "
                "FROM users WHERE username = %s;",
                (username,),
            )
            user = cur.fetchone()

            if user is None:
                error = "Incorrect username."
            elif not check_password_hash(user["password"], password):
                error = "Incorrect password."

            if error:
                flash(error, "warning")
            else:
                session.clear()
                session["user_id"] = user["id"]
                flash("Successfully logged in.", "info")
                return redirect(url_for("index"))

    return render_template("auth/login.html")


@bp.before_app_request
def load_logged_in_user():
    user_id = session.get("user_id")

    if user_id is None:
        g.user = None
    else:
        cur = get_cur()
        cur.execute(
            "SELECT id, username, mail, about FROM users WHERE id = %s;",
            (user_id,),
        )
        g.user = cur.fetchone()


@bp.route("/logout")
def logout():
    session.clear()
    flash("Successfully logged out.", "info")
    return redirect(url_for("index"))


@bp.route("/<int:id>", methods=("GET",))
def userinfo(id):
    cur = get_cur()
    cur.execute("SELECT id, username, about FROM users WHERE id = %s;", (id,))
    user = cur.fetchone()
    about = markdown(
        user["about"], extensions=["nl2br", "tables", "fenced_code"]
    )

    per_page = 5
    page, _, offset = get_page_args(per_page=per_page)

    cur.execute("SELECT COUNT(*) FROM posts WHERE author_id = %s;", (id,))
    total = cur.fetchone()[0]

    cur.execute(
        "SELECT id, title, body, created, modified, author_id, views "
        "FROM posts WHERE author_id = %s ORDER BY created DESC "
        "LIMIT %s OFFSET %s;",
        (id, per_page, offset),
    )
    posts = cur.fetchall()

    return render_template(
        "auth/userinfo.html",
        user=user,
        about=about,
        posts=posts,
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


@bp.route("/<int:id>/update", methods=("GET", "POST"))
def update(id):
    cur = get_cur()
    cur.execute(
        "SELECT id, username, mail, about, password FROM users WHERE id = %s;",
        (id,),
    )
    user = cur.fetchone()
    if user["id"] != g.user["id"]:
        flash("Invalid access.", "warning")
        return redirect(url_for("auth.userinfo", id=id))

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        password_confirm = request.form["password-confirm"]
        mail = request.form["mail"]
        about = request.form["about"]
        error = None

        if not username:
            error = "Username is required."
        elif not mail:
            error = "Mail address is required."
        elif re.match("[^\w]", username):
            error = "Username with only alphabets, numbers and underscores."
        elif re.match("[^\w]", password):
            error = "Password with only alphabets, numbers and underscores."

        if password:
            if not password_confirm:
                error = "Password confirmation is required."
            elif password != password_confirm:
                error = "Confirm password."

        about = about.replace("<script>", "&lt;script&gt;")

        if error:
            flash(error, "warning")
        else:
            conn = get_conn()
            cur.execute(
                "SELECT username FROM users WHERE username = %s;", (username,)
            )
            new_user = cur.fetchone()
            if new_user and new_user[0] != user["username"]:
                flash(f"User {username} is already registered.", "warning")
            else:
                cur.execute("SELECT mail FROM users WHERE mail = %s;", (mail,))
                new_mail = cur.fetchone()

                if new_mail and new_mail[0] != user["mail"]:
                    flash(f"Mail {mail} is already registered.", "warning")
                else:
                    if password:
                        cur.execute(
                            "UPDATE users SET username = %s, password = %s, "
                            "mail = %s, about = %s WHERE id = %s;",
                            (
                                username,
                                generate_password_hash(password),
                                mail,
                                about,
                                id,
                            ),
                        )
                    else:
                        cur.execute(
                            "UPDATE users SET username = %s, password = %s, "
                            "mail = %s, about = %s WHERE id = %s;",
                            (username, user["password"], mail, about, id,),
                        )
                    conn.commit()
                    flash("The user information successfully edited.", "info")
                    return redirect(url_for("auth.userinfo", id=id))

    return render_template("auth/update.html", user=user)

