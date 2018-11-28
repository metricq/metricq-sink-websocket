"""Module for route setup"""
from .views import websocket_handler


def setup_routes(app, cors):
    """Setup routes and cors for app."""
    resource = cors.add(app.router.add_resource("/ws"))
    cors.add(resource.add_route("GET", websocket_handler))
