#!/usr/bin/env node
import crypto from "node:crypto";
import dgram from "node:dgram";
import http from "node:http";
import { URL } from "node:url";

const argv = process.argv.slice(2);
const getArg = (name, fallback) => {
  const i = argv.indexOf(name);
  return i >= 0 && i + 1 < argv.length ? argv[i + 1] : fallback;
};
const getArgNumber = (name, fallback) => {
  const raw = getArg(name, String(fallback));
  const n = Number(raw);
  return Number.isFinite(n) ? n : fallback;
};
const getArgOptionalNumber = (name) => {
  const i = argv.indexOf(name);
  if (i < 0 || i + 1 >= argv.length) return null;
  const n = Number(argv[i + 1]);
  return Number.isFinite(n) ? n : null;
};

const udpHost = getArg("--udp-host", "0.0.0.0");
const udpPort = Number(getArg("--udp-port", "9000"));
const wsHost = getArg("--ws-host", "127.0.0.1");
const wsPort = Number(getArg("--ws-port", "8765"));
const defaultTagId = getArgNumber("--default-tag-id", 1);
const csv3Mode = getArg("--csv-3-mode", "auto"); // auto | idxy | xyz
const xScale = getArgNumber("--x-scale", 1.0);
const yScale = getArgNumber("--y-scale", 1.0);
const xOffset = getArgNumber("--x-offset", 0.0);
const yOffset = getArgNumber("--y-offset", 0.0);
const xMin = getArgOptionalNumber("--x-min");
const xMax = getArgOptionalNumber("--x-max");
const yMin = getArgOptionalNumber("--y-min");
const yMax = getArgOptionalNumber("--y-max");

const wsClients = new Set();
const lastSeen = new Map();

function toPayload(points) {
  return JSON.stringify({ tags: points });
}

function parsePacket(text) {
  const now = Date.now() / 1000;
  try {
    const obj = JSON.parse(text);
    if (Array.isArray(obj?.tags)) {
      return obj.tags
        .map((t) => normalizeTag(t, now, defaultTagId))
        .filter(Boolean);
    }
    const one = normalizeTag(obj, now, defaultTagId);
    return one ? [one] : [];
  } catch {
    const parts = text.split(",").map((x) => x.trim());
    if (parts.length === 3) {
      const a = Number(parts[0]);
      const b = Number(parts[1]);
      const c = Number(parts[2]);
      const parsedId = parseTagId(parts[0], null);
      const canUseIdxy = parsedId !== null && Number.isFinite(b) && Number.isFinite(c);
      const canUseXyz = Number.isFinite(a) && Number.isFinite(b) && Number.isFinite(c);

      if (csv3Mode === "idxy" && canUseIdxy) {
        return [{ id: parsedId, x: b, y: c, ts: now }];
      }
      if (csv3Mode === "xyz" && canUseXyz && Number.isFinite(defaultTagId)) {
        return [{ id: defaultTagId, x: a, y: c, ts: now }];
      }

      if (csv3Mode === "auto") {
        if (canUseIdxy) {
          return [{ id: parsedId, x: b, y: c, ts: now }];
        }
        if (canUseXyz && Number.isFinite(defaultTagId)) {
          return [{ id: defaultTagId, x: a, y: c, ts: now }];
        }
      }
    }
    return [];
  }
}

function parseTagId(raw, fallback) {
  if (raw === null || raw === undefined) return fallback;
  if (typeof raw === "number" && Number.isFinite(raw)) return Math.trunc(raw);

  const s = String(raw).trim();
  if (!s) return fallback;
  if (/^-?\d+$/.test(s)) return Number(s);
  const t = /^T(\d+)$/i.exec(s);
  if (t) return Number(t[1]);
  return fallback;
}

function normalizeTag(obj, ts, fallbackId = null) {
  if (!obj || typeof obj !== "object") return null;
  const id = parseTagId(obj.id ?? obj.tagId ?? obj.tag_id ?? obj.tag, fallbackId);
  const x = Number(obj.x ?? obj.posX ?? obj.pos_x);
  const yRaw = csv3Mode === "xyz" ? (obj.z ?? obj.posZ ?? obj.pos_z ?? obj.y ?? obj.posY ?? obj.pos_y) : (obj.y ?? obj.posY ?? obj.pos_y);
  const y = Number(yRaw);
  if (!Number.isFinite(id) || !Number.isFinite(x) || !Number.isFinite(y)) {
    return null;
  }
  return { id, x, y, ts };
}

function clamp(v, minV, maxV) {
  let out = v;
  if (Number.isFinite(minV)) out = Math.max(minV, out);
  if (Number.isFinite(maxV)) out = Math.min(maxV, out);
  return out;
}

function transformPoint(p) {
  if (!p || typeof p !== "object") return null;
  let x = Number(p.x) * xScale + xOffset;
  let y = Number(p.y) * yScale + yOffset;
  if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
  x = clamp(x, xMin, xMax);
  y = clamp(y, yMin, yMax);
  return { ...p, x, y };
}

function wsFrameFromText(text) {
  const payload = Buffer.from(text, "utf8");
  const len = payload.length;
  let header;
  if (len < 126) {
    header = Buffer.from([0x81, len]);
  } else if (len < 65536) {
    header = Buffer.alloc(4);
    header[0] = 0x81;
    header[1] = 126;
    header.writeUInt16BE(len, 2);
  } else {
    header = Buffer.alloc(10);
    header[0] = 0x81;
    header[1] = 127;
    header.writeBigUInt64BE(BigInt(len), 2);
  }
  return Buffer.concat([header, payload]);
}

function broadcast(points) {
  if (!points.length) return;
  const transformed = points.map((p) => transformPoint(p)).filter(Boolean);
  if (!transformed.length) return;
  for (const p of transformed) {
    lastSeen.set(p.id, p);
  }
  if (!wsClients.size) return;
  const frame = wsFrameFromText(toPayload(transformed));
  for (const socket of wsClients) {
    try {
      socket.write(frame);
    } catch {
      wsClients.delete(socket);
      socket.destroy();
    }
  }
}

const udp = dgram.createSocket("udp4");
udp.on("message", (buf) => {
  const text = buf.toString("utf8").trim();
  if (!text) return;
  const points = parsePacket(text);
  broadcast(points);
});
udp.bind(udpPort, udpHost, () => {
  console.log(`[bridge] UDP listening on ${udpHost}:${udpPort}`);
  console.log(`[bridge] csv-3-mode=${csv3Mode} default-tag-id=${defaultTagId}`);
  if (csv3Mode === "xyz") {
    console.log("[bridge] axis mapping: screen.x<-packet.x, screen.y<-packet.z, packet.y=depth");
  }
  console.log(
    `[bridge] transform x=(x*${xScale})+${xOffset} y=(y*${yScale})+${yOffset} clamp x:[${xMin ?? "-inf"},${xMax ?? "+inf"}] y:[${yMin ?? "-inf"},${yMax ?? "+inf"}]`
  );
});

const server = http.createServer((_req, res) => {
  res.writeHead(404);
  res.end("Not found");
});

server.on("upgrade", (req, socket) => {
  const key = req.headers["sec-websocket-key"];
  const upgrade = (req.headers["upgrade"] || "").toString().toLowerCase();
  if (!key || upgrade !== "websocket") {
    socket.destroy();
    return;
  }

  const accept = crypto
    .createHash("sha1")
    .update(`${key}258EAFA5-E914-47DA-95CA-C5AB0DC85B11`)
    .digest("base64");

  socket.write(
    [
      "HTTP/1.1 101 Switching Protocols",
      "Upgrade: websocket",
      "Connection: Upgrade",
      `Sec-WebSocket-Accept: ${accept}`,
      "",
      ""
    ].join("\r\n")
  );

  wsClients.add(socket);
  socket.on("close", () => wsClients.delete(socket));
  socket.on("error", () => wsClients.delete(socket));
  socket.on("end", () => wsClients.delete(socket));

  if (lastSeen.size) {
    socket.write(wsFrameFromText(toPayload([...lastSeen.values()])));
  }
});

server.listen(wsPort, wsHost, () => {
  console.log(`[bridge] WebSocket on ws://${wsHost}:${wsPort}`);
});
