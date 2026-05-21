from __future__ import annotations

import json
import os
import smtplib
from email.message import EmailMessage
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs


BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"


class ValidationError(Exception):
    def __init__(self, message_key: str):
        super().__init__(message_key)
        self.message_key = message_key


MESSAGES = {
    "en": {
        "success": "Your message has been sent.",
        "error": "Something went wrong. Please try again.",
        "required": "Please complete all required fields.",
        "invalid_email": "Please enter a valid email address.",
        "honeypot": "Something went wrong. Please try again.",
    },
    "bg": {
        "success": "Вашето съобщение беше изпратено.",
        "error": "Нещо се обърка. Моля, опитайте отново.",
        "required": "Моля, попълнете всички задължителни полета.",
        "invalid_email": "Моля, въведете валиден имейл адрес.",
        "honeypot": "Нещо се обърка. Моля, опитайте отново.",
    },
}


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value


def env_flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)

    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


load_dotenv(ENV_FILE)


def message_set(lang: str | None) -> dict[str, str]:
    return MESSAGES.get(lang or "", MESSAGES["en"])


class ContactHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Accept")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def do_GET(self) -> None:
        if self.path in {"", "/"}:
            self.path = "/index.html"

        super().do_GET()

    def do_POST(self) -> None:
        if self.path.rstrip("/") != "/api/contact":
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        data = {}

        try:
            data = self.parse_form_data()
            messages = message_set(data.get("lang"))
            self.validate_form_data(data)
            self.send_contact_email(data)
        except ValidationError as error:
            messages = message_set(data.get("lang"))
            self.send_json(HTTPStatus.BAD_REQUEST, {
                "ok": False,
                "message": messages.get(error.message_key, messages["error"]),
            })
            return
        except Exception as error:
            print(f"Contact form error: {error}")
            messages = message_set(data.get("lang"))
            self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {
                "ok": False,
                "message": messages["error"],
            })
            return

        messages = message_set(data.get("lang"))
        self.send_json(HTTPStatus.OK, {
            "ok": True,
            "message": messages["success"],
        })

    def parse_form_data(self) -> dict[str, str]:
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length).decode("utf-8")
        parsed = parse_qs(raw_body, keep_blank_values=True)

        return {
            key: values[0].strip()
            for key, values in parsed.items()
        }

    def validate_form_data(self, data: dict[str, str]) -> None:
        required_fields = ("name", "company", "email", "phone", "message")

        for field in required_fields:
            if not data.get(field):
                raise ValidationError("required")

        if data.get("website"):
            raise ValidationError("honeypot")

        if "@" not in data["email"] or "." not in data["email"].split("@")[-1]:
            raise ValidationError("invalid_email")

    def send_contact_email(self, data: dict[str, str]) -> None:
        smtp_host = os.environ.get("SMTP_HOST")
        smtp_username = os.environ.get("SMTP_USERNAME")
        smtp_password = os.environ.get("SMTP_PASSWORD")
        smtp_port = int(os.environ.get("SMTP_PORT", "587"))
        smtp_use_ssl = env_flag("SMTP_USE_SSL", default=False)
        smtp_use_tls = env_flag("SMTP_USE_TLS", default=not smtp_use_ssl)
        contact_to = os.environ.get("CONTACT_TO", "office@gpc.bg")
        contact_from = os.environ.get("CONTACT_FROM") or smtp_username or contact_to

        if not smtp_host or not smtp_username or not smtp_password:
            raise RuntimeError(
                "The contact form is not configured yet. Add SMTP settings before using it."
            )

        message = EmailMessage()
        message["Subject"] = f"Website contact form: {data['name']} - {data['company']}"
        message["From"] = contact_from
        message["To"] = contact_to
        message["Reply-To"] = data["email"]
        message.set_content(
            "\n".join(
                [
                    "New website enquiry",
                    "",
                    f"Name: {data['name']}",
                    f"Company: {data['company']}",
                    f"Email: {data['email']}",
                    f"Phone: {data['phone']}",
                    "",
                    "Message:",
                    data["message"],
                ]
            )
        )

        smtp_class = smtplib.SMTP_SSL if smtp_use_ssl else smtplib.SMTP

        with smtp_class(smtp_host, smtp_port, timeout=30) as server:
            server.ehlo()

            if not smtp_use_ssl and smtp_use_tls:
                server.starttls()
                server.ehlo()

            server.login(smtp_username, smtp_password)
            server.send_message(message)

    def send_json(self, status_code: HTTPStatus, payload: dict[str, object]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    host = os.environ.get("APP_HOST", "127.0.0.1")
    port = int(os.environ.get("APP_PORT", "8000"))
    server = ThreadingHTTPServer((host, port), ContactHandler)
    print(f"Serving Green Project Company website on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
