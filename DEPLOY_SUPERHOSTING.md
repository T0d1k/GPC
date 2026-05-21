# Deploying on SuperHosting.bg with Setup Python App

This project is ready for SuperHosting.bg cPanel `Setup Python App` with Passenger/WSGI.

## Files used for production

- `server.py` - the main WSGI application and SMTP contact form logic
- `passenger_wsgi.py` - the Passenger entry point
- `requirements.txt` - dependency file
- `.env` - SMTP and runtime configuration

## 1. Create the Python application in cPanel

In `cPanel -> Setup Python App`, create a new application with:

- `Python version`: use a current Python 3 version available in your account
- `App Directory`: the folder where this project will live, for example `gpc_site`
- `App URI`: `/` if this site should open directly on the domain root
- `WSGI file location`: `passenger_wsgi.py`

After Setup Python App creates the environment, it also creates a default `passenger_wsgi.py`. Replace it with the one from this project.

## 2. Upload the project files

Upload these files into the application directory created by Setup Python App:

- `index.html`
- `bg.html`
- `styles.css`
- `script.js`
- `server.py`
- `passenger_wsgi.py`
- `requirements.txt`
- `img/`

You can keep the project outside `public_html`; Passenger will load it through the generated `.htaccess` rules.

## 3. Install dependencies

This project currently uses only the Python standard library, so `requirements.txt` is intentionally empty of packages.

You can still run:

```bash
pip install -r requirements.txt
```

inside the virtual environment to keep the deployment step consistent.

## 4. Create the `.env` file

Create a `.env` file in the same directory as `server.py`.

Example:

```env
APP_HOST=127.0.0.1
APP_PORT=8000
CONTACT_TO=office@gpc.bg
CONTACT_FROM=office@gpc.bg
SMTP_HOST=smtp.your-mail-provider.com
SMTP_PORT=587
SMTP_USERNAME=office@gpc.bg
SMTP_PASSWORD=replace-with-your-real-password
SMTP_USE_TLS=true
SMTP_USE_SSL=false
```

## 5. Restart the application

After uploading files or editing `.env`, restart the Python app:

- from `Setup Python App -> Restart`, or
- by touching the Passenger restart file:

```bash
touch ~/gpc_site/tmp/restart.txt
```

Replace `gpc_site` with your real app directory.

## 6. Production behavior

- The site pages are served by the WSGI app.
- Static assets such as `/styles.css`, `/script.js`, `/bg.html`, and `/img/...` are served directly by the same WSGI application.
- The contact form posts to `api/contact` and returns JSON responses.
- Validation, honeypot anti-spam protection, and SMTP sending are preserved.

## 7. Important note for the frontend

The form JavaScript now uses a relative `api/contact` endpoint in production, so it works whether the app is mounted at `/` or under a sub-URI in cPanel.

## 8. Local development

You can still run the app locally with:

```bash
python server.py
```

Then open:

```text
http://127.0.0.1:8000
```
