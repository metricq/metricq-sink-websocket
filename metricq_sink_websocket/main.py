import logging
import traceback

import asyncio
import click
import click_completion
import click_log

from aiohttp import web
import aiohttp_cors

from metricq import get_logger

from .routes import setup_routes
from .sink import Sink

logger = get_logger()

click_log.basic_config(logger)
logger.setLevel('INFO')
logger.handlers[0].formatter = logging.Formatter(fmt='%(asctime)s [%(levelname)-8s] [%(name)-20s] %(message)s')

click_completion.init()


async def start_background_tasks(app):
    app['sink'] = Sink(app['token'], app["management_url"], event_loop=app.loop)
    await app['sink'].connect()
    logger.info('Background task ready.')


async def cleanup_background_tasks(app):
    pass


def create_app(loop, token, management_url, management_exchange, port):
    app = web.Application(loop=loop)
    app['token'] = token
    app['management_url'] = management_url
    app['management_exchange'] = management_exchange
    app['last_perf_list'] = []

    app.on_startup.append(start_background_tasks)
    app.on_cleanup.append(cleanup_background_tasks)

    cors = aiohttp_cors.setup(app, defaults={
        # Allow all to read all CORS-enabled resources from
        # http://client.example.org.
        f"http://localhost:{port}": aiohttp_cors.ResourceOptions(
            allow_headers=("Content-Type", ),
        ),
    })

    setup_routes(app, cors)
    return app


def panic(loop, context):
    print("EXCEPTION: {}".format(context['message']))
    if context['exception']:
        print(context['exception'])
        traceback.print_tb(context['exception'].__traceback__)
    loop.stop()


@click.command()
@click.argument('management-url', default='amqp://localhost/')
@click.option('--token', default='metricq-sink-websocket')
@click.option('--management-exchange', default='metricq.management')
@click.option('--port', default='3000')
@click_log.simple_verbosity_option(logger)
def runserver_cmd(management_url, token, management_exchange, port):
    try:
        import uvloop
        asyncio.get_event_loop().close()
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        logger.info('using uvloop as event loop')
    except ImportError:
        logger.debug('using default event loop')

    loop = asyncio.get_event_loop()
    # loop.set_debug(True)
    # loop.set_exception_handler(panic)
    app = create_app(loop, token, management_url, management_exchange, port)
    # logger.info("starting management loop")
    web.run_app(app, port=port)
