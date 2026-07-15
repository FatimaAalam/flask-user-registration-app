from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash
from flask_mysqldb import MySQL
from datetime import datetime
import re
import os

app = Flask(__name__)
app.secret_key = "dev-secret-key-change-in-prod"

# --- MySQL config from environment variables ---
app.config['MYSQL_HOST']     = os.environ.get('DB_HOST', 'localhost')
app.config['MYSQL_USER']     = os.environ.get('DB_USER', 'flaskuser')
app.config['MYSQL_PASSWORD'] = os.environ.get('DB_PASSWORD', 'flaskpass')
app.config['MYSQL_DB']       = os.environ.get('DB_NAME', 'flaskdb')

mysql = MySQL(app)

# --- Create table if it doesn't exist ---
def init_db():
    cur = mysql.connection.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id            INT AUTO_INCREMENT PRIMARY KEY,
            full_name     VARCHAR(100),
            username      VARCHAR(50) UNIQUE,
            email         VARCHAR(100) UNIQUE,
            phone         VARCHAR(20),
            dob           DATE,
            password_hash VARCHAR(256),
            joined        DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    mysql.connection.commit()
    cur.close()


def validate_registration(data):
    errors = []

    if not data.get("full_name") or len(data["full_name"].strip()) < 2:
        errors.append("Full name must be at least 2 characters.")

    if not data.get("username") or len(data["username"].strip()) < 3:
        errors.append("Username must be at least 3 characters.")
    elif not re.match(r"^[a-zA-Z0-9_]+$", data["username"]):
        errors.append("Username can only contain letters, numbers, and underscores.")

    if not data.get("email") or not re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", data["email"]):
        errors.append("Please enter a valid email address.")

    if not data.get("phone") or not re.match(r"^\+?[\d\s\-]{7,15}$", data["phone"]):
        errors.append("Please enter a valid phone number.")

    if not data.get("dob"):
        errors.append("Date of birth is required.")
    else:
        try:
            dob = datetime.strptime(data["dob"], "%Y-%m-%d")
            age = (datetime.today() - dob).days // 365
            if age < 13:
                errors.append("You must be at least 13 years old to register.")
            if age > 120:
                errors.append("Please enter a valid date of birth.")
        except ValueError:
            errors.append("Invalid date of birth format.")

    password = data.get("password", "")
    if len(password) < 8:
        errors.append("Password must be at least 8 characters.")
    elif not re.search(r"[A-Z]", password):
        errors.append("Password must contain at least one uppercase letter.")
    elif not re.search(r"\d", password):
        errors.append("Password must contain at least one number.")

    if data.get("confirm_password") != password:
        errors.append("Passwords do not match.")

    return errors


@app.route("/", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        form_data = {
            "full_name":        request.form.get("full_name", "").strip(),
            "username":         request.form.get("username", "").strip(),
            "email":            request.form.get("email", "").strip().lower(),
            "phone":            request.form.get("phone", "").strip(),
            "dob":              request.form.get("dob", "").strip(),
            "password":         request.form.get("password", ""),
            "confirm_password": request.form.get("confirm_password", ""),
        }

        errors = validate_registration(form_data)

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("register.html", form_data=form_data)

        dob_obj = datetime.strptime(form_data["dob"], "%Y-%m-%d")
        age     = (datetime.today() - dob_obj).days // 365
        pw_hash = generate_password_hash(form_data["password"])

        # --- Save to MySQL ---
        try:
            init_db()
            cur = mysql.connection.cursor()
            cur.execute('''
                INSERT INTO users (full_name, username, email, phone, dob, password_hash)
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', (
                form_data["full_name"],
                form_data["username"],
                form_data["email"],
                form_data["phone"],
                form_data["dob"],
                pw_hash
            ))
            mysql.connection.commit()
            cur.close()
        except Exception as e:
            flash(f"Database error: {str(e)}", "error")
            return render_template("register.html", form_data=form_data)

        session["user"] = {
            "full_name": form_data["full_name"],
            "username":  form_data["username"],
            "email":     form_data["email"],
            "phone":     form_data["phone"],
            "dob":       dob_obj.strftime("%B %d, %Y"),
            "age":       age,
            "joined":    datetime.now().strftime("%B %d, %Y"),
            "initials":  "".join(p[0].upper() for p in form_data["full_name"].split()[:2]),
        }

        return redirect(url_for("profile"))

    return render_template("register.html", form_data={})
@app.route("/health")
def health():
    return {"status": "ok"}, 200

@app.route("/profile")
def profile():
    user = session.get("user")
    if not user:
        return redirect(url_for("register"))
    return render_template("profile.html", user=user)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("register"))


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
