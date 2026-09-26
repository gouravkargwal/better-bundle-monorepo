export function getHostMode(request: Request): "app" | "marketing" {
  const url = new URL(request.url);
  const host = url.hostname;
  return host.startsWith("app.") ? "app" : "marketing";
}
