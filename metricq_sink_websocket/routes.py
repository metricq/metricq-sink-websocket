"""Module for route setup"""

import aiohttp_cors  # type: ignore
from aiohttp import web

from .views import websocket_handler


def setup_routes(app: web.Application, cors: aiohttp_cors.CorsConfig) -> None:
    """Setup routes and cors for app."""
    resource = cors.add(app.router.add_resource("/"))
    cors.add(resource.add_route("GET", websocket_handler))
