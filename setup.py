from setuptools import setup

setup(name='metricq_sink_websocket',
      version='0.1',
      author='TU Dresden',
      python_requires=">=3.5",
      packages=['metricq_sink_websocket'],
      scripts=[],
      entry_points='''
      [console_scripts]
      metricq-sink-websocket=metricq_sink_websocket:runserver_cmd
      ''',
      install_requires=['aiohttp', 'aiohttp-cors', 'click', 'click-completion', 'click_log', 'colorama', 'metricq'])
