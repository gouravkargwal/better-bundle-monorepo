# Build stage
FROM golang:1.20-alpine AS builder
WORKDIR /app
COPY . .
RUN go build -o gorse ./cmd/gorse

# Runtime stage
FROM alpine:3.18
RUN apk add --no-cache ca-certificates
COPY --from=builder /app/gorse /usr/local/bin/gorse
EXPOSE 8088
CMD ["gorse", "server", "--config", "/etc/gorse/config.toml"]
