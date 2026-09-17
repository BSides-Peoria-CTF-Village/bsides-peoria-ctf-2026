# syntax=docker/dockerfile:1
ARG NODE_VERSION=26.5.0

FROM node:${NODE_VERSION}-alpine

ENV NODE_ENV=production


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
