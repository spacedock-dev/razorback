# ABOUTME: Unit test asserting the DAB adapter's per_trial_state_reset declaration.
# ABOUTME: AC-6 — must match §6.5 verbatim: agent_container, compose_services, host_workspace all True.


def test_dab_declares_all_three_reset_surfaces_true():
    from razorback.benchmarks.dab import per_trial_state_reset

    assert per_trial_state_reset == {
        "agent_container": True,
        "compose_services": True,
        "host_workspace": True,
    }
