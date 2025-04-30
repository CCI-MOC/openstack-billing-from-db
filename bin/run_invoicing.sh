#!/usr/bin/env sh

python -m openstack_billing_db.main \
    --upload-to-s3 True \
    --download-sql-dump-from-s3 True \
    --convert-sql-dump-file-to-sqlite True \
    --use-nerc-rates
