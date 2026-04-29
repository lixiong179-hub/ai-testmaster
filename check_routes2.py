from app.main import app

for route in app.routes:
    if hasattr(route, 'path'):
        methods = route.methods if hasattr(route, 'methods') else ''
        print(f'{methods} {route.path}')
