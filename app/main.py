"""Main application entry point for Cloud Run service."""

from flask import Flask, jsonify

app = Flask(__name__)


@app.route("/", methods=["GET"])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "service": "exchange-rates-ingestion"}), 200


@app.route("/ingest", methods=["POST"])
def ingest_exchange_rates():
    """Ingest exchange rates from Open Exchange Rates API to BigQuery."""
    # TODO: Implement exchange rates ingestion logic
    return jsonify({"message": "Ingestion endpoint - to be implemented"}), 200


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)