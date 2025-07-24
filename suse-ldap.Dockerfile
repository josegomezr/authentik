# syntax=docker/dockerfile:1
FROM penny01-dev.dmz-prg2.suse.org/goauthentik/ldap:2025.10.2

# Escalate privileges to re-create the certificate bundle
USER root

# from ca-certificates-suse package.
# get it from: /usr/share/pki/trust/anchors/SUSE_Trust_Root.crt.pem
#
# heads-up: Debian only takes *.crt files.
COPY SUSE_Trust_Root.crt.pem /usr/local/share/ca-certificates/suse-dmz.crt
RUN update-ca-certificates -v

# Drop back to unprivileged user
USER 1000
