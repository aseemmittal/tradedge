from flask import request, redirect, url_for, make_response, jsonify
from flask_admin import Admin, BaseView, expose
import requests


def register_admin_panel(app, basic_auth, read_licenses, write_licenses):
    class LicenseAdminView(BaseView):
        def is_accessible(self):
            if (
                request.endpoint == "licenses.login_page"
                or request.endpoint == "licenses.login"
            ):
                return True
            if request.cookies.get("logged_in") == "1":
                return True
            return False

        def inaccessible_callback(self, name, **kwargs):
            return redirect(url_for(".login_page"))

        @expose("/")
        def index(self):
            licenses = read_licenses()
            return self.render("admin/license_list.html", licenses=licenses)

        @expose("/add", methods=["GET", "POST"])
        def add(self):
            if request.method == "POST":
                name = request.form.get("name")
                license_key = request.form.get("license_key")
                if name and license_key:
                    licenses = read_licenses()
                    licenses.append({"name": name, "license_key": license_key})
                    write_licenses(licenses)
                    return redirect(url_for(".index"))
            return self.render("admin/license_add.html")

        @expose("/delete/<int:idx>", methods=["POST"])
        def delete(self, idx):
            licenses = read_licenses()
            if 0 <= idx < len(licenses):
                licenses.pop(idx)
                write_licenses(licenses)
            return redirect(url_for(".index"))

        @expose("/send", methods=["POST"])
        def send(self):
            req = request.get_json()
            data_template = req.get("data", "")
            print("Data template:", data_template)
            return jsonify({"status": "Data template received."}), 200
            licenses = read_licenses()
            results = []
            errors = []
            for lic in licenses:
                payload = data_template.replace("{license}", lic["license_key"])
                try:
                    resp = requests.post(
                        "https://webhook.pineconnector.com",
                        data=payload,
                        headers={"Content-Type": "text/plain"},
                        timeout=5,
                    )
                    if resp.status_code == 200:
                        results.append(
                            {
                                "license": lic["license_key"],
                                "name": lic.get("name", ""),
                                "status": "OK",
                                "response": resp.text,
                            }
                        )
                    else:
                        errors.append(
                            {
                                "license": lic["license_key"],
                                "name": lic.get("name", ""),
                                "status": f"Error {resp.status_code}",
                                "response": resp.text,
                            }
                        )
                except Exception as e:
                    errors.append(
                        {
                            "license": lic["license_key"],
                            "name": lic.get("name", ""),
                            "status": "Exception",
                            "response": str(e),
                        }
                    )
            status_msg = f"Sent {len(results)} requests successfully."
            if errors:
                status_msg += f" {len(errors)} errors occurred."
            return jsonify({"status": status_msg, "success": results, "errors": errors})

        @expose("/login", methods=["POST"])
        def login(self):
            if request.is_json:
                data = request.get_json()
                username = data.get("username")
                password = data.get("password")
            else:
                username = request.form.get("username")
                password = request.form.get("password")
            if (
                username == app.config["BASIC_AUTH_USERNAME"]
                and password == app.config["BASIC_AUTH_PASSWORD"]
            ):
                resp = make_response(redirect(url_for(".index")))
                resp.set_cookie("logged_in", "1", httponly=True, max_age=60 * 60 * 8)
                return resp
            else:
                return jsonify({"error": "Invalid username or password."}), 401

        @expose("/login", methods=["GET"])
        def login_page(self):
            return self.render("admin/login.html")

    admin = Admin(app, name="Tradedge Admin", template_mode="bootstrap3")
    admin.add_view(LicenseAdminView(name="Licenses", endpoint="licenses"))
