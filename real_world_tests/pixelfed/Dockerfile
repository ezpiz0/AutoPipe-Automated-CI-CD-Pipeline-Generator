# syntax=docker/dockerfile:1.4

FROM composer:2 AS builder
WORKDIR /app
COPY composer.json composer.lock ./
RUN --mount=type=cache,target=/tmp/cache composer install --no-dev --optimize-autoloader --no-scripts
COPY . .

FROM php:8.3-fpm-alpine
WORKDIR /var/www/html
COPY --from=builder /app .
CMD ["php-fpm"]

