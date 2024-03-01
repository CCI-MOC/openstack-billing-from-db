FROM python:3.12

RUN curl https://raw.githubusercontent.com/dumblob/mysql2sqlite/c6ab632eb3ad5798c85f643bd7ecf76ea2d3c63e/mysql2sqlite \
        --output /bin/mysql2sqlite && \
    chmod +x /bin/mysql2sqlite


WORKDIR /app
COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY src ./
COPY bin/run_invoicing.sh ./run_invoicing.sh

ENTRYPOINT ["./run_invoicing.sh"]
