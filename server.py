from __future__ import annotations

import json
import mimetypes
import os
import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Callable, Iterable
from urllib.parse import parse_qs, unquote
from wsgiref.simple_server import make_server


BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"
WSGIApplication = Callable[[dict, Callable], Iterable[bytes]]


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

TEXT_TYPES = {
    "application/javascript",
    "application/json",
    "application/xml",
    "image/svg+xml",
}
ALLOWED_STATIC_SUFFIXES = {
    ".css",
    ".gif",
    ".html",
    ".ico",
    ".jpeg",
    ".jpg",
    ".js",
    ".json",
    ".png",
    ".svg",
    ".txt",
    ".webp",
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


def message_set(lang: str | None) -> dict[str, str]:
    return MESSAGES.get(lang or "", MESSAGES["en"])


def make_headers(
    content_type: str,
    content_length: int,
    extra_headers: list[tuple[str, str]] | None = None,
) -> list[tuple[str, str]]:
    headers = [
        ("Content-Type", content_type),
        ("Content-Length", str(content_length)),
    ]

    if extra_headers:
        headers.extend(extra_headers)

    return headers


def cors_headers() -> list[tuple[str, str]]:
    return [
        ("Access-Control-Allow-Origin", "*"),
        ("Access-Control-Allow-Methods", "POST, OPTIONS"),
        ("Access-Control-Allow-Headers", "Content-Type, Accept"),
    ]


def json_response(
    start_response: Callable,
    status: str,
    payload: dict[str, object],
    extra_headers: list[tuple[str, str]] | None = None,
) -> list[bytes]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = make_headers("application/json; charset=utf-8", len(body), extra_headers)
    start_response(status, headers)
    return [body]


def empty_response(
    start_response: Callable,
    status: str,
    extra_headers: list[tuple[str, str]] | None = None,
) -> list[bytes]:
    headers = make_headers("text/plain; charset=utf-8", 0, extra_headers)
    start_response(status, headers)
    return [b""]


def text_response(
    start_response: Callable,
    status: str,
    text: str,
    content_type: str = "text/plain; charset=utf-8",
) -> list[bytes]:
    body = text.encode("utf-8")
    start_response(status, make_headers(content_type, len(body)))
    return [body]


def content_type_for(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    content_type = guessed or "application/octet-stream"

    if content_type.startswith("text/") or content_type in TEXT_TYPES:
        return f"{content_type}; charset=utf-8"

    return content_type


def safe_path(path_info: str) -> Path | None:
    relative = unquote(path_info or "/").lstrip("/")

    if not relative:
        relative = "index.html"

    requested = (BASE_DIR / relative).resolve()

    try:
        requested.relative_to(BASE_DIR)
    except ValueError:
        return None

    if requested.is_dir():
        requested = requested / "index.html"

    if requested.name.startswith("."):
        return None

    if requested.suffix.lower() not in ALLOWED_STATIC_SUFFIXES:
        return None

    return requested


def parse_form_data(environ: dict) -> dict[str, str]:
    try:
        content_length = int(environ.get("CONTENT_LENGTH") or "0")
    except ValueError:
        content_length = 0

    raw_body = environ["wsgi.input"].read(content_length).decode("utf-8")
    parsed = parse_qs(raw_body, keep_blank_values=True)

    return {
        key: values[0].strip()
        for key, values in parsed.items()
    }


def validate_form_data(data: dict[str, str]) -> None:
    required_fields = ("name", "company", "email", "phone", "message")

    for field in required_fields:
        if not data.get(field):
            raise ValidationError("required")

    if data.get("website"):
        raise ValidationError("honeypot")

    email = data["email"]

    if "@" not in email or "." not in email.split("@")[-1]:
        raise ValidationError("invalid_email")


def send_contact_email(data: dict[str, str]) -> None:
    smtp_host = os.environ.get("SMTP_HOST")
    smtp_username = os.environ.get("SMTP_USERNAME")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_use_ssl = env_flag("SMTP_USE_SSL", default=False)
    smtp_use_tls = env_flag("SMTP_USE_TLS", default=not smtp_use_ssl)
    contact_to = os.environ.get("CONTACT_TO", "office@gpc.bg")
    contact_from = os.environ.get("CONTACT_FROM") or smtp_username or contact_to

    if not smtp_host or not smtp_username or not smtp_password:
        raise RuntimeError("SMTP is not configured.")

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


def serve_static(environ: dict, start_response: Callable) -> list[bytes]:
    method = environ.get("REQUEST_METHOD", "GET").upper()
    path_info = environ.get("PATH_INFO", "/")
    target = safe_path(path_info)

    if target is None or not target.exists() or not target.is_file():
        return text_response(start_response, "404 Not Found", "Not Found")

    body = b"" if method == "HEAD" else target.read_bytes()
    start_response(
        "200 OK",
        make_headers(content_type_for(target), len(body)),
    )
    return [body]


def handle_contact(environ: dict, start_response: Callable) -> list[bytes]:
    method = environ.get("REQUEST_METHOD", "GET").upper()

    if method == "OPTIONS":
        return empty_response(start_response, "204 No Content", cors_headers())

    if method != "POST":
        return json_response(
            start_response,
            "405 Method Not Allowed",
            {"ok": False, "message": "Method not allowed."},
            cors_headers() + [("Allow", "POST, OPTIONS")],
        )

    data: dict[str, str] = {}

    try:
        data = parse_form_data(environ)
        validate_form_data(data)
        send_contact_email(data)
    except ValidationError as error:
        messages = message_set(data.get("lang"))
        return json_response(
            start_response,
            "400 Bad Request",
            {
                "ok": False,
                "message": messages.get(error.message_key, messages["error"]),
            },
            cors_headers(),
        )
    except Exception as error:
        print(f"Contact form error: {error}")
        messages = message_set(data.get("lang"))
        return json_response(
            start_response,
            "500 Internal Server Error",
            {
                "ok": False,
                "message": messages["error"],
            },
            cors_headers(),
        )

    messages = message_set(data.get("lang"))
    return json_response(
        start_response,
        "200 OK",
        {
            "ok": True,
            "message": messages["success"],
        },
        cors_headers(),
    )


def application(environ: dict, start_response: Callable) -> list[bytes]:
    method = environ.get("REQUEST_METHOD", "GET").upper()
    path_info = environ.get("PATH_INFO", "/") or "/"

    if path_info.rstrip("/") == "/api/contact":
        return handle_contact(environ, start_response)

    if method not in {"GET", "HEAD"}:
        return text_response(start_response, "405 Method Not Allowed", "Method Not Allowed")

    return serve_static(environ, start_response)


def main() -> None:
    host = os.environ.get("APP_HOST", "127.0.0.1")
    port = int(os.environ.get("APP_PORT", "8000"))
    print(f"Serving Green Project Company website on http://{host}:{port}")

    with make_server(host, port, application) as server:
        server.serve_forever()


load_dotenv(ENV_FILE)


if __name__ == "__main__":
    main()
