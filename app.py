from flask import Flask, redirect, render_template, request, url_for

from college_data import get_available_college_data, refresh_college_data
from college_filters import (
    RESULT_LIMITS, SORT_OPTIONS, filter_colleges, get_filter_options,
    limit_colleges, sort_colleges, validate_filters,
)


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
    states, institution_types = get_filter_options(records)
    selected, filters, validation_messages = validate_filters(request.args, states, institution_types)
    matching = filter_colleges(records, filters)
    displayed = limit_colleges(sort_colleges(matching, filters["sort"]), filters["limit"])
    return render_template(
        "explorer.html", colleges=displayed, record_count=len(records),
        matching_count=len(matching), selected=selected, states=states,
        institution_types=institution_types, sort_options=SORT_OPTIONS,
        result_limits=RESULT_LIMITS, validation_messages=validation_messages,
        metadata=metadata, source=source, status_message=status_message,
        refresh_message=refresh_message,
    )


@app.route("/college/<int:school_id>")
def college_detail(school_id):
    records = get_available_college_data()[0]
    states, institution_types = get_filter_options(records)
    selected, _, _ = validate_filters(request.args, states, institution_types)
    back_query = {key: value for key, value in selected.items() if key in request.args}
    back_url = url_for("explorer", **back_query)
    for college in records:
        if college["school_id"] == school_id:
            return render_template("college_detail.html", college=college, back_url=back_url)
    return render_template("college_detail.html", college=None, back_url=back_url), 404


@app.route("/simulator")
def simulator():
    return render_template("simulator_placeholder.html")


if __name__ == "__main__":
    app.run()
