#!/usr/bin/env sh

python -m openstack_billing_db.main \
    --upload-to-s3 True \
    --download-coldfront-data True \
    --download-sql-dump-from-s3 True \
    --convert-sql-dump-file-to-sqlite True \
    --rate-cpu-su 0.013 \
    --rate-gpu-a100-su 1.803 \
    --rate-gpu-v100-su 1.214 \
    --rate-gpu-k80-su 0.463 \
    --rate-gpu-a2-su 0.463
