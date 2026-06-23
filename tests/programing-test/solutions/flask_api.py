"""Flask REST API with full CRUD operations.

A simple in-memory item store demonstrating Create, Read, Update, Delete
via a RESTful JSON API.

Run:
    pip install flask
    python flask_api.py

Endpoints:
    GET    /items          - List all items
    GET    /items/<id>     - Get a single item
    POST   /items          - Create a new item
    PUT    /items/<id>     - Update an existing item
    DELETE /items/<id>     - Delete an item
"""

from flask import Flask, jsonify, request

app = Flask(__name__)

# In-memory store keyed by integer id.
items: dict[int, dict] = {}
next_id: int = 1


@app.route("/items", methods=["GET"])
def list_items():
    """Return all items."""
    return jsonify(list(items.values())), 200


@app.route("/items/<int:item_id>", methods=["GET"])
def get_item(item_id: int):
    """Return a single item by id."""
    item = items.get(item_id)
    if item is None:
        return jsonify({"error": "Item not found"}), 404
    return jsonify(item), 200


@app.route("/items", methods=["POST"])
def create_item():
    """Create a new item from JSON body."""
    global next_id

    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 415

    data = request.get_json()
    name = data.get("name")
    if not name:
        return jsonify({"error": "'name' is required"}), 400

    item = {
        "id": next_id,
        "name": name,
        "description": data.get("description", ""),
    }
    items[next_id] = item
    next_id += 1
    return jsonify(item), 201


@app.route("/items/<int:item_id>", methods=["PUT"])
def update_item(item_id: int):
    """Update an existing item."""
    if item_id not in items:
        return jsonify({"error": "Item not found"}), 404

    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 415

    data = request.get_json()
    item = items[item_id]

    if "name" in data:
        item["name"] = data["name"]
    if "description" in data:
        item["description"] = data["description"]

    return jsonify(item), 200


@app.route("/items/<int:item_id>", methods=["DELETE"])
def delete_item(item_id: int):
    """Delete an item by id."""
    if item_id not in items:
        return jsonify({"error": "Item not found"}), 404

    del items[item_id]
    return jsonify({"message": "Item deleted"}), 200


if __name__ == "__main__":
    app.run(debug=True, port=5000)
