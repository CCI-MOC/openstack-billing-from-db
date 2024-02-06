FROM python:3.12

COPY requirements.txt /app/requirements.txt

RUN curl https://raw.githubusercontent.com/dumblob/mysql2sqlite/c6ab632eb3ad5798c85f643bd7ecf76ea2d3c63e/mysql2sqlite \
        --output /bin/mysql2sqlite \
    && pip install -r /app/requirements.txt

COPY src /app
COPY bin/run_invoicing.sh /app/run_invoicing.sh

ENTRYPOINT ["/app/run_invoicing.sh"]
