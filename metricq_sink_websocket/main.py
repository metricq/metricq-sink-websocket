import logging
import traceback
import sys

import asyncio
import click
import click_completion  # type: ignore
import click_log  # type: ignore

from aiohttp import web
import aiohttp_cors  # type: ignore

from metricq import get_logger

from .routes import setup_routes
from .sink import Sink
from .version import version as client_version

logger = get_logger()

click_log.basic_config(logger)
logger.setLevel("INFO")
logger.handlers[0].formatter = logging.Formatter(
    fmt="%(asctime)s [%(levelname)-8s] [%(name)-20s] %(message)s"
)

click_completion.init()


async def metricq_disconnect_handler(app):
    logger.info("MetricQ is running...")

    try:
        await app["sink"].stopped()
    except Exception as e:
        logger.fatal("Something happend to our MetricQ Connection: {}", e)

        # When the MetricQ connection fails, there is a reconnect timeout during
        # which reconnects are tried. If the reconnect fails for the whole time,
        # it is considered gone for good and the client should exit. However,
        # for some reason, the websocket sink keeps going in a zombie state. To
        # mitigate this, we increased the reconnect timeout in MetricQ and this
        # commit. For now, we brutally use sys.exit to shutdown.
        sys.exit(2)


async def start_background_tasks(app):
    app["sink"] = Sink(
        app["token"],
        app["management_url"],
        client_version=client_version,
    )
    await app["sink"].connect()
    logger.info("Background task ready.")

    asyncio.create_task(metricq_disconnect_handler(app))


async def cleanup_background_tasks(app):
    pass


def create_app(token, management_url, management_exchange, port):
    app = web.Application()
    app["token"] = token
    app["management_url"] = management_url
    app["management_exchange"] = management_exchange
    app["last_perf_list"] = []

    app.on_startup.append(start_background_tasks)
    app.on_cleanup.append(cleanup_background_tasks)

    cors = aiohttp_cors.setup(
        app,
        defaults={
            # Allow all to read all CORS-enabled resources from
            f"http://localhost:{port}": aiohttp_cors.ResourceOptions(
                allow_headers=("Content-Type",)
            )
        },
    )

    setup_routes(app, cors)
    return app


@click.command()
@click.argument("management-url", default="amqp://localhost/")
@click.option("--token", default="metricq-sink-websocket")
@click.option("--management-exchange", default="metricq.management")
@click.option("--host", default="0.0.0.0")
@click.option("--port", default="3000")
@click.version_option(client_version)
@click_log.simple_verbosity_option(logger)
def runserver_cmd(management_url, token, management_exchange, host, port):
    try:
        import uvloop  # type: ignore

        uvloop.install()
        logger.info("using uvloop as event loop")
    except ImportError:
        logger.debug("using default event loop")

    app = create_app(token, management_url, management_exchange, port)
    web.run_app(app, host=host, port=port)
