FROM python:3.12-slim

# Defaults for the container. The socket directory is bind-mounted at
# /run/herdr, so no host path or home directory is baked in.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp \
    HERDR_SOCKET_PATH=/run/herdr/herdr.sock \
    HERDR_MCP_TRANSPORT=streamable-http \
    HERDR_MCP_BIND=0.0.0.0:8000 \
    HERDR_MCP_STATE_DIR=/state

WORKDIR /opt/herdr-mcp
COPY src/ /opt/herdr-mcp/src/
COPY bin/ /opt/herdr-mcp/bin/
RUN chmod +x /opt/herdr-mcp/bin/herdr-mcp \
 && mkdir -p /state && chmod 1777 /state

# The Herdr CLI is not bundled: bind-mount the host's (Linux) herdr binary at
# /usr/local/bin/herdr so the container speaks the running server's protocol.
# Run the container as the uid that owns the socket (`user:` in compose, or
# `docker run -u "$(id -u):$(id -g)"`); the socket is mode 0600.
USER 65534:65534
EXPOSE 8000
ENTRYPOINT ["/opt/herdr-mcp/bin/herdr-mcp"]
CMD ["--http"]
