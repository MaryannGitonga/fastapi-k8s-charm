#!/usr/bin/env python3

import ops
import logging

# log messages can be retrieved using juju debug-log
logger = logging.getLogger(__name__)

class FastAPIDemoCharm(ops.CharmBase):
    """
    Charm the service
    """

    def __init__(self, framework: ops.Framework) -> None:
        super().__init__(framework)
        self.pebble_service_name = "fastapi-service"
        framework.observe(self.on.demo_server_pebble_ready, self._on_demo_server_pebble_ready)

    def _on_demo_server_pebble_ready(self, event: ops.PebbleReadyEvent) -> None:
        """
        Define & start a workload using the Pebble API
        """

        # get a reference (the container attribute) on the PebbleReadyEvent
        container = event.workload

        # add initial Pebble config layer using the Pebble API
        container.add_layer("fastapi_demo", self._pebble_layer, combine=True)

        # make Pebble re-evaluate its plan, ensuring any services are started if enabled
        container.replan()

        self.unit.status = ops.ActiveStatus()

    @property
    def _pebble_layer(self) -> ops.pebble.Layer:
        """
        A Pebble layer for the FastAPI demo services.
        """

        command = ' '.join([
            'uvicorn',
            'api_demo_server.app:app',
            '--host=0.0.0.0',
            '--port=8000',
        ])

        pebble_layer: ops.pebble.LayerDict = {
            'summary': 'FastAPI demo service',
            'description': 'pebble config layer for FastAPI demo server',
            'services': {
                self.pebble_service_name: {
                    'override': 'replace',
                    'summary': 'fastapi demo',
                    'command': command,
                    'startup': 'enabled',
                }
            }
        }

        return ops.pebble.Layer(pebble_layer)
    
if __name__ == "__main__": # pragma: no cover
    ops.main(FastAPIDemoCharm)