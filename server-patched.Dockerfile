FROM penny01-dev.dmz-prg2.suse.org/goauthentik/server:2025.10.2

USER root
RUN apt update && apt install -y --no-install-recommends vim git-core && rm -rf /var/cache/apt /var/lib/apt/lists/

COPY ./authentik/ /authentik

USER 1000
