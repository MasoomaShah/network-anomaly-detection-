"""
pi_server.py — Lightweight API Server for Raspberry Pi
========================================================
Run on the Pi:  python pi_server.py

Exposes two endpoints:
  GET  /metrics          → collect and return live network metrics
  POST /tool/<name>      → execute a specific fix command locally on Pi
"""

import os
import sys
import json
import logging
from flask import Flask, jsonify, request

# Ensure we can import from the local agent/collector folders
_BASE = os.path.dirname(os.path.abspath(__file__))
if _BASE not in sys.path:
    sys.path.insert(0, _BASE)

from collector.metrics import get_all_metrics as get_current_metrics

from agent.tools import TOOL_DEFINITIONS

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s")
log = logging.getLogger("pi_server")

@app.route("/metrics", methods=["GET"])
def metrics():
    """Fetch live metrics from this Pi."""
    try:
        data = get_current_metrics()
        return jsonify(data)
    except Exception as e:
        log.error(f"Metrics error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/tool/<name>", methods=["POST"])
def execute_tool(name):
    """Execute a specific tool command on this Pi."""
    try:
        # Find the tool in our registry
        tool = next((t for t in TOOL_DEFINITIONS if t["name"] == name), None)
        if not tool:
            return jsonify({"error": f"Tool '{name}' not found"}), 404

        # Get input from request body
        input_data = request.json or {}
        input_str = input_data.get("input_str", "")
        
        log.info(f"Executing tool: {name} with input: '{input_str}'")
        
        # For 'restart_interface', we run it in the background so we don't 
        # kill the HTTP connection before sending the response.
        if name == "restart_interface":
            import threading
            import time
            def do_restart():
                time.sleep(1)
                tool["func"](input_str)
            threading.Thread(target=do_restart).start()
            return jsonify({"result": "Interface restart initiated in background. Connection will drop momentarily."})

        # Execute the tool's function
        # Note: We call the underlying function directly to avoid recursive remote calls
        result = tool["func"](input_str)
        
        return jsonify({"result": result})

    except Exception as e:
        log.error(f"Tool error ({name}): {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    # Run on all interfaces (0.0.0.0) so the laptop can reach it
    log.info("Starting Pi Remote Server on port 5000...")
    app.run(host="0.0.0.0", port=5000)
