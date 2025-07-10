FROM penny01-dev.dmz-prg2.suse.org/goauthentik/server:2025.10.2

USER root

COPY ./authentik/ /authentik

USER 1000
