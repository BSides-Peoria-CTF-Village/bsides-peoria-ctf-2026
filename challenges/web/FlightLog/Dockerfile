# syntax=docker/dockerfile:1

# Comments are provided throughout this file to help you get started.
# If you need more help, visit the Dockerfile reference guide at
# https://docs.docker.com/go/dockerfile-reference/

# Want to help us make this template better? Share your feedback here: https://forms.gle/ybq9Krt8jtBL3iCk7

ARG NODE_VERSION=26.5.0

FROM node:${NODE_VERSION}-alpine

# Use production node environment by default.
ENV NODE_ENV=production


WORKDIR /usr/src/app

COPY src/chall ./src/chall
COPY src/bot ./src/bot
COPY flag.txt ./flag.txt

# Download dependencies as a separate step to take advantage of Docker's caching.
# Leverage a cache mount to /root/.npm to speed up subsequent builds.
# The Node application and its dependency manifests live under src/chall.
RUN --mount=type=bind,source=src/chall/package.json,target=package.json \
    --mount=type=bind,source=src/chall/package-lock.json,target=package-lock.json \
    --mount=type=cache,target=/root/.npm \
    npm ci --omit=dev

# The application runs as `node` and stores submitted notes here.
RUN mkdir -p ./src/chall/notes \
    && chown node:node ./src/chall/notes

# Run the application as a non-root user.
USER node

# Copy the application source into the working directory.

# Expose the port that the application listens on.
EXPOSE 3000

# Run the application.
CMD ["node", "src/chall/app.js"]
