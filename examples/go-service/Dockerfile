# syntax=docker/dockerfile:1.4

FROM golang:1.21-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN --mount=type=cache,target=/go/pkg/mod go mod download
COPY . .
RUN --mount=type=cache,target=/root/.cache/go-build go build -o app .

FROM alpine:latest
WORKDIR /app
COPY --from=builder /app/app .
CMD ["./app"]

