# ABOUTME: DAB benchmark's per_trial_state_reset declaration (§6.5, AC-6).
# ABOUTME: Read by rk validate and rk runs show in later milestones; declared at the adapter root.

per_trial_state_reset: dict[str, bool] = {
    "agent_container": True,
    "compose_services": True,
    "host_workspace": True,
}
