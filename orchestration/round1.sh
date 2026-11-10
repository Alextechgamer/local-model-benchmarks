#!/bin/bash
cd /e/strata-tests/orch-r1 || exit 1
./dispatch.sh core muse-spark-1.3-contributor-free 1 &
./dispatch.sh structures muse-spark-1.3-contributor-free 1 &
./dispatch.sh world longcat-2.5-preview-free 1 &
./dispatch.sh runtime longcat-2.5-preview-free 1 &
./dispatch.sh ui space-bunny-free 1 &
wait; echo ROUND1 DONE
