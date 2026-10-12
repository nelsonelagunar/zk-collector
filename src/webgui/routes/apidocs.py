"""
API Docs Routes - OpenAPI spec + Swagger UI at /api/docs
"""

from pathlib import Path

from flask import Blueprint, abort, send_file

openapi_path = Path(__file__).resolve().parents[3] / "docs" / "openapi.yaml"

apidocs_bp = Blueprint("apidocs", __name__)

SWAGGER_UI_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>ZK-Collector API Reference</title>
  <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script>
    SwaggerUIBundle({ url: '/api/openapi.yaml', dom_id: '#swagger-ui' });
  </script>
</body>
</html>
"""


@apidocs_bp.route("/docs")
def swagger_ui():
    """Interactive Swagger UI for the API reference"""
    return SWAGGER_UI_HTML


@apidocs_bp.route("/openapi.yaml")
def openapi_spec():
    """Machine-readable OpenAPI 3.1 spec"""
    if not openapi_path.exists():
        abort(404, description="OpenAPI spec not bundled with this deployment")
    return send_file(openapi_path, mimetype="application/yaml")


@apidocs_bp.route("/openapi.json")
def openapi_spec_json():
    """JSON variant of the OpenAPI spec"""
    import json as jsonlib

    import yaml

    if not openapi_path.exists():
        abort(404, description="OpenAPI spec not bundled with this deployment")
    with openapi_path.open() as fh:
        return jsonlib.loads(jsonlib.dumps(yaml.safe_load(fh)))
