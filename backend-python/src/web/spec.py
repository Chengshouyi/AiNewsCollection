from flask_pydantic_spec import FlaskPydanticSpec

spec = FlaskPydanticSpec(
    'flask', 
    title='AI News Collection API',
    version='1.0.0',
    description='AI 新聞爬蟲與收集系統',
)

def init_spec(app):
    """初始化並註冊 spec 至 Flask app"""
    spec.register(app)
    
    # 設定 OpenAPI JSON 端點
    @app.route("/openapi.json")
    def get_openapi_json():
        from flask import jsonify
        return jsonify(spec.to_dict())
    
    # 設定 Swagger UI 端點
    @app.route("/docs")
    def get_documentation():
        from flask import render_template_string
        
        # 簡易的 Swagger UI HTML
        html = """
        <!DOCTYPE html>
        <html>
          <head>
            <title>API Documentation</title>
            <meta charset="utf-8"/>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <link rel="stylesheet" type="text/css" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@4/swagger-ui.css" />
          </head>
          <body>
            <div id="swagger-ui"></div>
            <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@4/swagger-ui-bundle.js"></script>
            <script>
              window.onload = function() {
                const ui = SwaggerUIBundle({
                  url: "/openapi.json",  
                  dom_id: "#swagger-ui",
                  deepLinking: true,
                  presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIBundle.SwaggerUIStandalonePreset
                  ],
                  layout: "BaseLayout",
                  docExpansion: "list"
                });
                window.ui = ui;
              };
            </script>
          </body>
        </html>
        """
        return render_template_string(html)
