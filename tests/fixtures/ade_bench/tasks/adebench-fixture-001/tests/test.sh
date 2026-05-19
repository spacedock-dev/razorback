#!/bin/sh
# AC-3 fixture: the nop agent writes nothing, so the test fails and reward=0.
# This is intentional — Task 1 validates the translator + harbor wiring, not the agent.
if [ -f /work/answer.txt ] && grep -q "hello-adebench" /work/answer.txt; then
    mkdir -p /logs/verifier
    echo '{"reward": 1.0}' > /logs/verifier/reward.json
else
    mkdir -p /logs/verifier
    echo '{"reward": 0.0}' > /logs/verifier/reward.json
fi
exit 0
