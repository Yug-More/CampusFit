from flask import Flask, redirect, render_template, url_for


app = Flask(__name__)


@app.route("/")
def home():
    return redirect(url_for("explorer"))


@app.route("/explorer")
def explorer():
    return render_template("explorer.html")


@app.route("/simulator")
def simulator():
    return render_template("simulator_placeholder.html")


if __name__ == "__main__":
    app.run()
