FROM penny01-dev.dmz-prg2.suse.org/goauthentik/server:2025.10.2

ARG GIT_BUILD_HASH
USER root
RUN apt update && apt install -y --no-install-recommends vim git-core && rm -rf /var/cache/apt /var/lib/apt/lists/

COPY ./authentik/ /authentik
COPY ./suse_settings/user_settings.py /data/user_settings.py

ENV GIT_BUILD_HASH=$GIT_BUILD_HASH

USER 1000
