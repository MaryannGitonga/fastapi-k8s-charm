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
        self.container = self.unit.get_container("demo-server")

        framework.observe(self.on.demo_server_pebble_ready, self._on_demo_server_pebble_ready)
        framework.observe(self.on.config_changed, self._on_config_changed)

    def _on_demo_server_pebble_ready(self, event: ops.PebbleReadyEvent) -> None:
        """
        Define & start a workload using the Pebble API
        """

        self._update_layer_and_restart()
    
    def _on_config_changed(self, event: ops.ConfigChangedEvent) -> None:
        port = self.config["server-port"]

        if port == 22:
            self.unit.status = ops.BlockedStatus("Invalid port number, port 22 is reserved for SSH")
            return
    
        logger.debug("New application port is requested: %s", port)
        self._update_layer_and_restart()
    
    def _update_layer_and_restart(self) -> None:
        """
        Define & start a workload using the Pebble API.

        Need to specify the right entrypoint and env config for specific workload.
        """

        self.unit.status = ops.MaintenanceStatus('Assembling Pebble layers')
        try:
            self.container.add_layer('fastapi_demo', self._pebble_layer, combine=True)
            logger.info("Added updated layer 'fastapi_demo' to Pebble plan")

            # tell Pebble to incorporate the changes, including restarting the service if required
            self.container.replan()
            logger.info(f"Replanned with '{self.pebble_service_name}' service")

            self.unit.status = ops.ActiveStatus()
        except (ops.pebble.APIError, ops.pebble.ConnectionError):
            self.unit.status = ops.MaintenanceStatus('Waiting for Pebble in workload container')

    @property
    def _pebble_layer(self) -> ops.pebble.Layer:
        """
        A Pebble layer for the FastAPI demo services.
        """

        command = ' '.join([
            'uvicorn',
            'api_demo_server.app:app',
            '--host=0.0.0.0',
            f"--port={self.config['server-port']}",
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