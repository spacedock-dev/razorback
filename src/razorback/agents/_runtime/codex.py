# ABOUTME: Codex runtime adapter stub (NotImplementedError per D2 default).
# ABOUTME: Functional implementation lands when a consumer surfaces (spec §4.3.1 + §8.4).


def build_inner_agent(**kwargs):
    raise NotImplementedError(
        "codex runtime adapter is not implemented. "
        "Per spec §4.3.1 + §8.4, codex ships when a consumer surfaces; "
        "Phase 3 ships claude only per D2 default."
    )
