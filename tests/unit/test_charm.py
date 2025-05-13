import ops
from ops import testing

from charm import FastAPIDemoCharm

def test_pebble_layer():
    ctx = testing.Context(FastAPIDemoCharm)
    container = testing.Container(name = "demo-server", can_connect = True)
    state_in = testing.State(
        containers = {container},
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
                # since the env is empty, Layer.to_dict() will not include it
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