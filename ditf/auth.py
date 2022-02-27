import functools

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
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_conn, get_cur

bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.route("/register", methods=("GET", "POST"))
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        mail = request.form["mail"]
        error = None

        if not username:
            error = "Username is required."
        elif not password:
            error = "Password is required."
        elif not mail:
            error = "Mail address is required."

        if error is None:
            conn = get_conn()
            cur = get_cur()
            cur.execute(
                "SELECT username FROM users WHERE username = %s;", (username,)
            )
            if cur.fetchone():
                error = f"User {username} is already registered."
            else:
                cur.execute("SELECT mail FROM users WHERE mail = %s;", (mail,))

                if cur.fetchone():
                    error = f"Mail {mail} is already registered."
                else:
                    cur.execute(
                        "INSERT INTO users (username, password, mail) "
                        "VALUES (%s, %s, %s);",
                        (username, generate_password_hash(password), mail),
                    )
                    conn.commit()
                    return redirect(url_for("auth.login"))

        flash(error)

    return render_template("auth/register.html")


@bp.route("/login", methods=("GET", "POST"))
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        error = None

        cur = get_cur()
        cur.execute("SELECT * FROM users WHERE username = %s;", (username,))
        user = cur.fetchone()

        if user is None:
            error = "Incorrect username."
        elif not check_password_hash(user["password"], password):
            error = "Incorrect password."

        if error is None:
            session.clear()
            session["user_id"] = user["id"]
            return redirect(url_for("index"))

        flash(error)

    return render_template("auth/login.html")


@bp.before_app_request
def load_logged_in_user():
    user_id = session.get("user_id")

    if user_id is None:
        g.user = None
    else:
        cur = get_cur()
        cur.execute("SELECT * FROM users WHERE id = %s;", (user_id,))
        g.user = cur.fetchone()


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for("auth.login"))

        return view(**kwargs)

    return wrapped_view
