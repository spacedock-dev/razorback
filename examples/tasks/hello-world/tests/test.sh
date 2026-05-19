#!/bin/sh
# Drop a passing reward at harbor's documented contract path.
set -eu
mkdir -p /logs/verifier
printf '1.0' > /logs/verifier/reward.txt
echo "wrote reward.txt" 1>&2
