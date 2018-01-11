FROM ubuntu:latest

ENV DEBIAN_FRONTEND noninteractive
ENV LANG C.UTF-8

RUN \
    apt-get update          &&  \
    apt-get upgrade --yes   &&  \
    apt-get install --yes       \
        bzip2                   \
        curl                    \
        vim

RUN \
    curl -o /tmp/miniconda3.sh https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh    &&  \
    /bin/bash /tmp/miniconda3.sh -f -b -p /opt/anaconda3                                                &&  \
    rm -rf /tmp/miniconda3.sh

ENV PATH=/opt/anaconda3/bin:$PATH

RUN \
    conda upgrade --yes --all           &&  \
    pip install -v -v -v motor tornado

WORKDIR /srv
ADD app.py docker-entrypoint.sh /srv/
RUN chmod a+x docker-entrypoint.sh

CMD ["python", "app.py"]
ENTRYPOINT ["./docker-entrypoint.sh"]
