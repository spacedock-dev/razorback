# ABOUTME: ade-bench's per_trial_state_reset declaration (§6.5).
# ABOUTME: compose_services=False per §6.5 example ("postgres state leaks across trials").

per_trial_state_reset: dict[str, bool] = {
    "agent_container": True,
    "compose_services": False,
    "host_workspace": True,
}
