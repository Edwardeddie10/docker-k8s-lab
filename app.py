import os
import socket
from flask import Flask, jsonify

app = Flask(__name__)

@app.get("/")
def home():
    return jsonify(
        message="Hello from Kubernetes Version 2!",
        version=os.getenv("APP_VERSION", "v1"),
        pod=socket.gethostname(),
    )

@app.get("/health")
def health():
    return jsonify(status="healthy"), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)