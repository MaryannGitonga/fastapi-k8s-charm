#!/usr/bin/env python3

import ops
import logging

from charms.data_platform_libs.v0.data_interfaces import DatabaseCreatedEvent
from charms.data_platform_libs.v0.data_interfaces import DatabaseRequires

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

        # the 'relation_name': comes from the 'charmcraft.yaml file'
        # the 'database_name': name of the db that the app requires
        self.database = DatabaseRequires(self, relation_name="database", database_name="names_db")

        framework.observe(self.on.demo_server_pebble_ready, self._on_demo_server_pebble_ready)
        framework.observe(self.on.config_changed, self._on_config_changed)
        framework.observe(self.database.on.database_created, self._on_database_created)
        framework.observe(self.database.on.endpoints_changed, self._on_database_created)
        framework.observe(self.on.collect_unit_status, self._on_collect_status)

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
                    'environment': self.app_environment
                }
            }
        }

        return ops.pebble.Layer(pebble_layer)

    @property
    def app_environment(self) -> dict[str, str]:
        """
        Creates a dictionary containing env variables for the app.
        It retrieves the db auth data by calling the `fetch_postgres_relation_data`
        method & uses it to populate the dict. If any value isn't present
        it will be set to None. The method returns the dict as output.
        """
        db_data = self.fetch_postgres_relation_data()
        if not db_data:
            return {}
        
        env = {
            key: value
            for key, value in {
                "DEMO_SERVER_DB_HOST": db_data.get("db_host", None),
                "DEMO_SERVER_DB_PORT": db_data.get("db_port", None),
                "DEMO_SERVER_DB_USER": db_data.get("db_username", None),
                "DEMO_SERVER_DB_PASSWORD": db_data.get("db_password", None),
            }.items()
            if value is not None
        }

        return env
    
    # ----- event handlers/hooks -----
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
            logger.debug('Waiting for Pebble in workload container')

    def _on_demo_server_pebble_ready(self, event: ops.PebbleReadyEvent) -> None:
        """
        Define & start a workload using the Pebble API
        """

        self._update_layer_and_restart()
    
    def _on_config_changed(self, event: ops.ConfigChangedEvent) -> None:
        port = self.config["server-port"]

        if port == 22:
            # the collect-status handler will set the status to blocked.
            logger.debug('Invalid port number: 22 is reserved for SSH')
    
        logger.debug("New application port is requested: %s", port)
        self._update_layer_and_restart()

    def _on_database_created(self, event: DatabaseCreatedEvent) -> None:
        """ event is fired when postgres is created """
        self._update_layer_and_restart()
    
    def _on_collect_status(self, event: ops.CollectStatusEvent) -> None:
        port = self.config['server-port']

        if port == 22:
            event.add_status(ops.BlockedStatus('Invalid port number, port 22 is reserved for SSH'))

        if not self.model.get_relation('database'):
            # need the user to do 'juju integrate'
            event.add_status(ops.BlockedStatus('Waiting for database relation'))
        elif not self.database.fetch_relation_data():
            # need the charms to finish integrating
            event.add_status(ops.WaitingStatus('Waiting for database relation'))
        
        try:
            status = self.container.get_service(self.pebble_service_name)
        except (ops.pebble.APIError, ops.pebble.ConnectionError, ops.ModelError):
            event.add_status(ops.MaintenanceStatus('Waiting for Pebble in workload container'))
        else:
            if not status.is_running():
                event.add_status(ops.MaintenanceStatus('Waiting for the service to start up'))
        
        # if nothing is wrong, then status is active
        event.add_status(ops.ActiveStatus())

    # ----- end of event handlers/hooks -----

    # ----- util methods -----
    def fetch_postgres_relation_data(self) -> dict[str, str]:
        """
        Fetch postgres relation data

        The function retrieves relation data from a postgres database using
        the `fetch_relation_data` method of the `database` object. The retrieved data
        is logged for debugging purposes and any non-empty data is processed to extract
        endpoint info (username & password). The processed data is returned as a dict.
        If no data is retrieved, the unit is set to waiting status & the program
        exits with a zero status code.
        """
        relations = self.database.fetch_relation_data()
        logger.debug('Got following database data: %s', relations)

        for data in relations.values():
            if not data:
                continue
            logger.info('New PSQL database endpoint is %s', data['endpoints'])
            host, port = data['endpoints'].split(':')
            db_data = {
                'db_host': host,
                'db_port': port,
                'db_username': data['username'],
                'db_password': data['password']
            }

            return db_data

        return {}
    # ----- end of util methods -----
    
if __name__ == "__main__": # pragma: no cover
    ops.main(FastAPIDemoCharm)