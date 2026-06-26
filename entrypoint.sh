#!/bin/sh
set -e

# Link Nintendo Switch key files from /config into the location nsz expects
for keyfile in prod.keys keys.txt; do
    if [ -f "/config/$keyfile" ] && [ ! -e "/root/.switch/$keyfile" ]; then
        ln -s "/config/$keyfile" "/root/.switch/$keyfile"
    fi
done

exec "$@"
