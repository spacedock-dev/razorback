# ABOUTME: Per-harbor-minor translation layer (§6.1).
# ABOUTME: razorback pins harbor 0.6.6; this package gains a module per supported minor.

from razorback.compat.harbor_0_6_6 import spec_to_job_config

__all__ = ["spec_to_job_config"]
