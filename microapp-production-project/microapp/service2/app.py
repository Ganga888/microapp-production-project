from flask import Flask, jsonify
import socket, os

app = Flask(__name__)
SERVICE_NAME = os.environ.get("SERVICE_NAME", "service2")
VERSION = os.environ.get("VERSION", "v1")

@app.route("/")
def root():
    return jsonify({
        "service": SERVICE_NAME,
        "version": VERSION,
        "hostname": socket.gethostname(),
        "message": f"Hello from {SERVICE_NAME} ({VERSION})"
    })

@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok"}), 200

@app.route("/readyz")
def readyz():
    return jsonify({"status": "ready"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
