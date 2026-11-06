from flask import Flask, redirect, render_template, request, url_for

from college_data import get_available_college_data, refresh_college_data


app = Flask(__name__)


@app.route("/")
def home():
    return redirect(url_for("explorer"))


@app.route("/explorer", methods=["GET", "POST"])
def explorer():
    refresh_message = ""
    if request.method == "POST":
        successful, refresh_message = refresh_college_data()
        if successful:
            return redirect(url_for("explorer", refreshed="1"))
    records, metadata, source, status_message = get_available_college_data()
    if request.args.get("refreshed") == "1" and not refresh_message:
        refresh_message = "Refresh successful. The saved college data is shown below."
    return render_template(
        "explorer.html", colleges=records[:20], record_count=len(records),
        metadata=metadata, source=source, status_message=status_message,
        refresh_message=refresh_message,
    )


@app.route("/simulator")
def simulator():
    return render_template("simulator_placeholder.html")


if __name__ == "__main__":
    app.run()
