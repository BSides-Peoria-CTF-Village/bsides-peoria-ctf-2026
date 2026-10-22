# syntax=docker/dockerfile:1
ARG NODE_VERSION=26.12.1

FROM node:${NODE_VERSION}-alpine

ENV NODE_ENV=production

# Puppeteer's own Chrome download targets glibc and silently no-ops on
# Alpine's musl libc, so the bot's puppeteer.launch() fails at runtime
# with "Could not find Chrome" unless we install Alpine's own chromium
# package and point Puppeteer at it instead.
RUN apk add --no-cache chromium nss freetype harfbuzz ca-certificates ttf-freefont
ENV PUPPETEER_SKIP_DOWNLOAD=true
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium-browser

WORKDIR /usr/src/app

COPY src/chall ./src/chall
COPY src/bot ./src/bot
COPY flag.txt ./flag.txt

RUN --mount=type=bind,source=src/chall/package.json,target=package.json \
    --mount=type=bind,source=src/chall/package-lock.json,target=package-lock.json \
    --mount=type=cache,target=/root/.npm \
    npm ci --omit=dev

RUN mkdir -p ./src/chall/notes \
    && chown node:node ./src/chall/notes

USER node

EXPOSE 3000

CMD ["node", "src/chall/app.js"]
