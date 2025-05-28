from flask import Flask, request, jsonify
from flask_basicauth import BasicAuth
import json
import os
from datetime import datetime, timedelta

app = Flask(__name__)

# Basic Authentication configuration
with open("credentials.json", "r") as cred_file:
    credentials = json.load(cred_file)
app.config["BASIC_AUTH_USERNAME"] = credentials.get("username")
app.config["BASIC_AUTH_PASSWORD"] = credentials.get("password")
basic_auth = BasicAuth(app)

# File to store data
DATA_FILE = "./data.json"

# Ensure the data file exists
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump({}, f)  # Initialize as an empty dictionary


def read_licenses():
    with open("./licenses.json", "r") as f:
        return json.load(f)


def write_licenses(licenses):
    with open("./licenses.json", "w") as f:
        json.dump(licenses, f, indent=2)


@app.route("/" + credentials.get("webhookPath"), methods=["POST"])
# @basic_auth.required
def post_data():
    try:
        # Parse JSON data from the request
        data = request.json
        data_set = data.get("dataSet")
        data_set["action"] = data_set.get("action", "").upper()
        print(data_set)

        # Validate required fields
        if not data_set or not all(
            k in data_set for k in ["name", "price", "action", "time", "counter"]
        ):
            return jsonify({"error": "Invalid JSON format or missing fields."}), 400

        # Extract and save only the required fields
        filtered_data = {
            "price": data_set["price"],
            "action": data_set["action"],
            "time": data_set["time"],
        }

        # Read existing data from the file
        with open(DATA_FILE, "r") as f:
            data_map = json.load(f)

        # Ensure the data_map is a dictionary
        if not isinstance(data_map, dict):
            data_map = {}

        # Append the new data under the corresponding name
        if data_set["name"] not in data_map:
            data_map[data_set["name"]] = []

        if filtered_data["action"] == "EXIT":
            data_map[data_set["name"]].append(filtered_data)
            last_buy = next(
                (
                    entry
                    for entry in reversed(data_map[data_set["name"]])
                    if entry["action"] == "BUY"
                ),
                None,
            )
            if last_buy:
                data_map[data_set["name"]].append(
                    {
                        "price": str(
                            float(data_set["price"]) - float(last_buy["price"])
                        ),
                        "action": "PnL",
                        "time": data_set["time"],
                    }
                )
        elif filtered_data["action"] == "COVER":
            data_map[data_set["name"]].append(filtered_data)
            last_short = next(
                (
                    entry
                    for entry in reversed(data_map[data_set["name"]])
                    if entry["action"] == "SHORT"
                ),
                None,
            )
            if last_short:
                data_map[data_set["name"]].append(
                    {
                        "price": str(
                            float(float(last_short["price"] - data_set["price"]))
                        ),
                        "action": "PnL",
                        "time": data_set["time"],
                    }
                )
        elif filtered_data["action"] == "SHORT":
            if data_set["counter"] == "-2":
                last_buy = next(
                    (
                        entry
                        for entry in reversed(data_map[data_set["name"]])
                        if entry["action"] == "BUY"
                    ),
                    None,
                )
                if last_buy:
                    data_map[data_set["name"]].append(
                        {
                            "price": str(
                                float(float(last_buy["price"] - data_set["price"]))
                            ),
                            "action": "PnL",
                            "time": data_set["time"],
                        }
                    )
            data_map[data_set["name"]].append(filtered_data)
        elif filtered_data["action"] == "BUY":
            if data_set["counter"] == "2":
                last_short = next(
                    (
                        entry
                        for entry in reversed(data_map[data_set["name"]])
                        if entry["action"] == "SHORT"
                    ),
                    None,
                )
                if last_short:
                    data_map[data_set["name"]].append(
                        {
                            "price": str(
                                float(float(last_short["price"] - data_set["price"]))
                            ),
                            "action": "PnL",
                            "time": data_set["time"],
                        }
                    )
            data_map[data_set["name"]].append(filtered_data)

        # Write updated data back to the file
        with open(DATA_FILE, "w") as f:
            json.dump(data_map, f, indent=2)

        return (
            jsonify(
                {
                    "message": "Data received successfully.",
                    "receivedData": filtered_data,
                }
            ),
            200,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/", methods=["GET"])
@basic_auth.required
def get_data():
    try:
        stock_name = request.args.get("name")
        # Read data from the file
        with open(DATA_FILE, "r") as f:
            data = json.load(f)

        if stock_name:
            # Return data for the specific stock name
            stock_data = data.get(stock_name)
            if stock_data is None:
                return (
                    jsonify({"error": f"No data found for stock name: {stock_name}"}),
                    404,
                )
            # Remove data older than 2 months
            two_months_ago = datetime.now() - timedelta(days=60)
            filtered_stock_data = [
                entry
                for entry in data.get(stock_name, [])
                if datetime.strptime(entry["time"], "%Y-%m-%dT%H:%M:%SZ")
                >= two_months_ago
            ]

            # Update the file with filtered data
            data[stock_name] = filtered_stock_data
            with open(DATA_FILE, "w") as f:
                json.dump(data, f, indent=2)
            # Filter data to return only the last 31 days
            one_month_ago = datetime.now() - timedelta(days=31)
            filtered_data = [
                entry
                for entry in stock_data
                if datetime.strptime(entry["time"], "%Y-%m-%dT%H:%M:%SZ")
                >= one_month_ago
            ]
            return jsonify(filtered_data), 200

        # Return all data if no stock name is provided
        return jsonify([]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Import and register the admin panel
from admin_panel import register_admin_panel

register_admin_panel(app, basic_auth, read_licenses, write_licenses)

if __name__ == "__main__":
    app.run(port=3000)
