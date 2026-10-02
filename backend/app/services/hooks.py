"""Outbound integrations: generic webhooks (Zapier/Make/n8n/Pipedream), Discord, Slack, Telegram.

Events: sale.completed (to the creator), transfer.received (to the receiver), test.ping.
Webhook bodies are signed: header X-SmartSharing-Signature: sha256=<hex hmac of raw body with the integration secret>.
"""
import hashlib
import hmac
import ipaddress
import json
import logging
import secrets
import socket
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

import httpx
from pymongo.database import Database

from ..util import new_id, now_utc
from .wallet import WalletError

log = logging.getLogger("smartsharing.hooks")
_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="hooks")

TYPES = {"webhook", "discord", "slack", "telegram"}
EVENTS = {"sale.completed", "transfer.received"}


class IntegrationError(WalletError):
    code = "integration_error"


def _public_https(url: str) -> None:
    p = urlparse(url)
    if p.scheme != "https" or not p.hostname:
        raise IntegrationError("URL must be https://")
    try:
        infos = socket.getaddrinfo(p.hostname, p.port or 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise IntegrationError("URL host does not resolve")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise IntegrationError("URL must point to a public host")


def validate_config(kind: str, cfg: dict) -> dict:
    if kind not in TYPES:
        raise IntegrationError(f"type must be one of {sorted(TYPES)}")
    if kind == "telegram":
        tok, chat = str(cfg.get("bot_token", "")).strip(), str(cfg.get("chat_id", "")).strip()
        if ":" not in tok or not chat:
            raise IntegrationError("telegram needs bot_token (from @BotFather) and chat_id")
        return {"bot_token": tok, "chat_id": chat}
    url = str(cfg.get("url", "")).strip()
    if kind == "discord" and not url.startswith(("https://discord.com/api/webhooks/", "https://discordapp.com/api/webhooks/")):
        raise IntegrationError("Discord URL must start with https://discord.com/api/webhooks/")
    if kind == "slack" and not url.startswith("https://hooks.slack.com/"):
        raise IntegrationError("Slack URL must start with https://hooks.slack.com/")
    _public_https(url)
    out = {"url": url}
    if kind == "webhook":
        out["secret"] = cfg.get("secret") or "whsec_" + secrets.token_hex(16)
    return out


def masked(cfg: dict) -> dict:
    out = dict(cfg)
    for k in ("url", "bot_token"):
        if out.get(k):
            v = out[k]
            out[k] = v[:28] + "…" + v[-4:] if len(v) > 36 else v[:6] + "…"
    if out.get("secret"):
        out["secret"] = out["secret"][:10] + "…"
    return out


def _text(event: str, data: dict) -> str:
    if event == "sale.completed":
        s = f"💸 New sale: {data['asset_name']} ({data['license_name']}) — {data['price']:,} credits"
        s += f", you earned {data['creator_amount']:,}"
        if data.get("discount_code"):
            s += f" · code {data['discount_code']}"
        return s + f" · buyer {data['buyer']}"
    if event == "transfer.received":
        return f"📥 {data['from']} sent you {data['amount']:,} credits" + (f" — “{data['memo']}”" if data.get("memo") else "") + ". Accept it in your wallet."
    return "✅ SmartSharing test notification — your integration works."


def _deliver(d: Database, integ: dict, event: str, data: dict) -> dict:
    cfg, kind = integ["config"], integ["type"]
    body_obj = {"id": new_id("evt"), "event": event, "created_at": now_utc().isoformat(), "data": data}
    try:
        if kind == "webhook":
            raw = json.dumps(body_obj, separators=(",", ":")).encode()
            sig = hmac.new(cfg["secret"].encode(), raw, hashlib.sha256).hexdigest()
            r = httpx.post(cfg["url"], content=raw, timeout=6, headers={
                "Content-Type": "application/json", "User-Agent": "SmartSharing-Webhooks/1.0",
                "X-SmartSharing-Event": event, "X-SmartSharing-Signature": f"sha256={sig}"})
        elif kind == "discord":
            r = httpx.post(cfg["url"], json={"content": _text(event, data), "username": "SmartSharing"}, timeout=6)
        elif kind == "slack":
            r = httpx.post(cfg["url"], json={"text": _text(event, data)}, timeout=6)
        else:
            r = httpx.post(f"https://api.telegram.org/bot{cfg['bot_token']}/sendMessage",
                           json={"chat_id": cfg["chat_id"], "text": _text(event, data)}, timeout=6)
        ok, status, err = 200 <= r.status_code < 300, r.status_code, None if r.is_success else r.text[:200]
    except httpx.HTTPError as e:
        ok, status, err = False, None, str(e)[:200]
    rec = {"_id": new_id("dlv"), "integration_id": integ["_id"], "user_id": integ["user_id"], "event": event,
           "ok": ok, "status": status, "error": err, "created_at": now_utc()}
    d.integration_deliveries.insert_one(rec)
    d.integrations.update_one({"_id": integ["_id"]}, {"$set": {"last_delivery": {"ok": ok, "status": status,
                                                                                  "at": rec["created_at"], "event": event}}})
    return rec


def emit(d: Database, user_id: str, event: str, data: dict) -> None:
    """Fire-and-forget fan-out to the user's active integrations subscribed to `event`."""
    try:
        integs = list(d.integrations.find({"user_id": user_id, "active": True, "events": event}))
    except Exception:  # never let notifications break a sale
        log.exception("integration lookup failed")
        return
    for i in integs:
        _pool.submit(_safe_deliver, d, i, event, data)


def _safe_deliver(d, integ, event, data):
    try:
        _deliver(d, integ, event, data)
    except Exception:
        log.exception("delivery failed for %s", integ["_id"])


def send_test(d: Database, integ: dict) -> dict:
    sample = {"asset_id": "sample", "asset_name": "Sample Asset", "license_name": "Personal", "price": 499,
              "creator_amount": 439, "buyer": "Test B.", "receipt": "SS-TEST0000"}
    return _deliver(d, integ, "test.ping", sample)
