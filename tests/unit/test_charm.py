import ops
from ops import testing

from charm import FastAPIDemoCharm

def test_pebble_layer():
    ctx = testing.Context(FastAPIDemoCharm)
    container = testing.Container(name = "demo-server", can_connect = True)
    relation = testing.Relation(
        endpoint="database",
        interface="postgresql_client",
        remote_app_name="postgresql-k8s",
        remote_app_data={
            "endpoints": "example.com:5432",
            "username": "foo",
            "password": "bar",
        },
    )

    state_in = testing.State(
        containers = {container},
        relations={relation},
        leader = True,
    )

    state_out = ctx.run(ctx.on.pebble_ready(container), state_in)

    # expected plan after Pebble ready with default config
    expected_plan = {
        "services": {
            "fastapi-service": {
                "override": "replace",
                "summary": "fastapi demo",
                "command": "uvicorn api_demo_server.app:app --host=0.0.0.0 --port=8000",
                "startup": "enabled",
                'environment': {
                    "DEMO_SERVER_DB_HOST": "example.com",
                    "DEMO_SERVER_DB_PORT": "5432",
                    "DEMO_SERVER_DB_USER": "foo",
                    "DEMO_SERVER_DB_PASSWORD": "bar",
                }
            }
        }
    }

    # check that we have the expected plan
    assert state_out.get_container(container.name).plan == expected_plan

    # check the unit status is active
    assert state_out.unit_status == testing.ActiveStatus()

    # check the service was started
    assert state_out.get_container(container.name).service_statuses["fastapi-service"] == ops.pebble.ServiceStatus.ACTIVE

def test_config_changed():
    ctx = testing.Context(FastAPIDemoCharm)
    container = testing.Container(name="demo-server", can_connect=True)
    
    state_in = testing.State(
        containers={container},
        config={"server-port": 8080},
        leader=True,
    )

    state_out = ctx.run(ctx.on.config_changed(), state_in)
    assert "--port=8080" in state_out.get_container(container.name).layers["fastapi_demo"].services["fastapi-service"].command

def test_config_changed_invalid_port():
    ctx = testing.Context(FastAPIDemoCharm)
    container = testing.Container(name="demo-server", can_connect=True)
    state_in = testing.State(
        containers={container},
        config={"server-port": 22},
        leader=True,
    )

    state_out = ctx.run(ctx.on.config_changed(), state_in)
    assert state_out.unit_status == testing.BlockedStatus("Invalid port number, port 22 is reserved for SSH")

def test_relation_data():
    ctx = testing.Context(FastAPIDemoCharm)
    relation = testing.Relation(
        endpoint="database",
        interface="postgresql_client",
        remote_app_name="postgresql-k8s",
        remote_app_data={
            "endpoints": "example.com:5432",
            "username": "foo",
            "password": "bar",
        },
    )

    container = testing.Container(name="demo-server", can_connect=True)
    state_in = testing.State(
        containers={container},
        relations={relation},
        leader=True
    )

    state_out = ctx.run(ctx.on.relation_changed(relation), state_in)

    assert state_out.get_container(container.name).layers["fastapi_demo"].services["fastapi-service"].environment == {
        "DEMO_SERVER_DB_HOST": "example.com",
        "DEMO_SERVER_DB_PORT": "5432",
        "DEMO_SERVER_DB_USER": "foo",
        "DEMO_SERVER_DB_PASSWORD": "bar",
    }

def test_on_database_blocked():
    ctx = testing.Context(FastAPIDemoCharm)
    container = testing.Container(name="demo-server", can_connect=True)
    state_in = testing.State(
        containers={container},
        leader=True,
    )

    state_out = ctx.run(ctx.on.collect_unit_status(), state_in)

    assert state_out.unit_status == testing.BlockedStatus('Waiting for database relation')

def test_get_db_info_action():
    ctx = testing.Context(FastAPIDemoCharm)
    relation = testing.Relation(
        endpoint="database",
        interface="postgresql-client",
        remote_app_name="postgresql-k8s",
        remote_app_data={
            "endpoints": "example.com:5432",
            "username": "foo",
            "password": "bar",
        },
    )

    container = testing.Container(name="demo-server", can_connect=True)
    state_in = testing.State(
        containers={container},
        relations={relation},
        leader=True,
    )

    ctx.run(ctx.on.action("get-db-info", params={"show-password": False}), state_in)

    assert ctx.action_results == {
        "db-host": "example.com",
        "db-port": "5432",
    }

def test_get_db_info_action_show_password():
    ctx = testing.Context(FastAPIDemoCharm)
    relation = testing.Relation(
        endpoint="database",
        interface="postgresql_client",
        remote_app_name="postgresql-k8s",
        remote_app_data={
            "endpoints": "example.com:5432",
            "username": "foo",
            "password": "bar",
        },
    )
    container = testing.Container(name="demo-server", can_connect=True)
    state_in = testing.State(
        containers={container},
        relations={relation},
        leader=True,
    )

    ctx.run(ctx.on.action("get-db-info", params={"show-password": True}), state_in)

    assert ctx.action_results == {
        "db-host": "example.com",
        "db-port": "5432",
        "db-username": "foo",
        "db-password": "bar",
    }