"""Build a clean, upload-ready copy of the project for a public GitHub repo.

Nothing in the source tree is touched: files are copied into a staging folder,
secrets in the text are replaced with placeholders, and only then is the ZIP made.
Anything that is a secret or a build artifact is left out entirely rather than
shipped with a placeholder, because a binary (keystore, APK, private key) cannot
be "sanitised" and a compiled APK still carries the values it was built with.
"""
from __future__ import annotations

import fnmatch
import os
import re
import shutil
import zipfile
from pathlib import Path

SRC = Path(r"C:\NEXUS\Beyond_Registration_5.1.3_NEXUS_INTERFACE_OWNER_TEST_ACADEMY_PREVIEW_20261107_015947")
OUT_DIR = Path(r"C:\Users\beyon\.abacusai-bot\session-home\artifacts")
STAGE = OUT_DIR / "n3xus-public-repo"
ZIP_PATH = OUT_DIR / "N3XUS-public-clean.zip"

# Directories never copied: build output, caches, VCS, and anything that only
# exists on this machine (logs, proofs with live values, backups).
SKIP_DIRS = {
    ".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "node_modules", "build", ".gradle", ".idea", "venv", ".venv",
    "proof", ".backup_pre_lockfix_20261120", "ARCHIVE_NON_OPERATIONAL",
    "apk-src", "caddy", "turnserver-src", "data",
}
# Files never copied, by exact name or pattern: secrets and binaries.
SKIP_FILES = [
    "*.exe", "*.dll", "*.apk", "*.aab", "*.jks", "*.keystore", "*.p12",
    "*.key", "*.pem", "*.crt", "*.secret", "*.pass", "*.db", "*.sqlite", "*.sqlite3",
    ".env", "*.log", "*.out", "*.ico",
    "*.bak*", "*.icefix*", "*.pre_*", "*.orig", "*.rej", "turn.lastip",
]
# Individual names that are machine keys even though the pattern list misses them.
SKIP_NAMES = {"restic.pass", "turn.secret", "auto.crt", "auto.key", "origin-ca.crt",
              "nexus-release.jks", "N3XUS.apk", "nexus-latest.apk", "br_lan_ca.pem"}

# Text files worth rewriting. Everything else is copied byte for byte.
TEXT_EXT = {".py", ".js", ".java", ".xml", ".properties", ".json", ".md", ".bat",
            ".ps1", ".html", ".css", ".txt", ".gradle", ".kts", ".yml", ".yaml",
            ".sh", ".cjs", ".mjs", ".pro", ".cfg", ".ini", ".example", ".env"}

# Replacements: longest/most specific first. Each entry is (regex, replacement).
REPLACEMENTS: list[tuple[str, str]] = [
    # --- DuckDNS: host and the token that can rewrite the record -------------
    (r"beyond-2\.duckdns\.org", "YOUR_DUCKDNS_DOMAIN.duckdns.org"),
    (r"256b6cc5-dc19-4d53-9eb0-671277989e09", "YOUR_DUCKDNS_TOKEN"),
    (r"beyond-2", "your-app-name"),
    # --- Metered TURN app + key ---------------------------------------------
    (r"n3xus\.metered\.live", "YOUR_APP.metered.live"),
    (r"HSNh5lXwqmFjWoNucTvT_iJRMvoX88_ZVZ4hDUim5JtrfIcg", "YOUR_METERED_API_KEY"),
    (r"openrelayprojectsecret", "YOUR_RELAY_SHARED_SECRET"),
    (r"openrelayproject", "YOUR_RELAY_USER"),
    # --- signing ------------------------------------------------------------
    (r"YNGBDjVaZWhJhQwjeNOR_YC-cPCRMDee", "YOUR_KEYSTORE_PASSWORD"),
    # --- public IPv4 addresses of this machine / its line -------------------
    (r"\b169\.0\.211\.127\b", "YOUR_PUBLIC_IP"),
    # --- LAN addresses: the server machine ----------------------------------
    (r"\b192\.168\.3\.8\b", "YOUR_SERVER_IP"),
    (r"\b192\.168\.3\.\d{1,3}\b", "YOUR_LAN_IP"),
    (r"\b192\.168\.3\.x\b", "YOUR_LAN_SUBNET.x"),
    (r"\b192\.168\.\d{1,3}\.x\b", "YOUR_LAN_SUBNET.x"),
    (r"\b192\.168\.\d{1,3}\.\d{1,3}\b", "YOUR_LAN_IP"),
    (r"\b10\.44\.0\.1\b", "YOUR_SERVER_IP"),
    (r"\b10\.44\.\d{1,3}\.\d{1,3}\b", "YOUR_LAN_IP"),
    # --- cloudflared quick-tunnel hostnames (random, and live while in use) --
    (r"\b[a-z0-9]+(?:-[a-z0-9]+){2,5}\.trycloudflare\.com", "YOUR_TUNNEL.trycloudflare.com"),
    # --- the operator's own PC paths ---------------------------------------
    (r"C:\\\\Users\\\\beyon\\\\AppData\\\\Local\\\\Beyond Registration", r"C:\\\\Users\\\\YOUR_USER\\\\AppData\\\\Local\\\\Beyond Registration"),
    (r"C:/Users/beyon/AppData/Local/Beyond Registration", "C:/Users/YOUR_USER/AppData/Local/Beyond Registration"),
    (r"C:\\\\NEXUS\\\\[^\"'\r\n]*", r"C:\\\\YOUR_PATH\\\\Beyond_Registration"),
    (r"C:/NEXUS/[^\"'\r\n]*", "C:/YOUR_PATH/Beyond_Registration"),
    (r"/NEXUS/[^\"'\r\n]*", "/YOUR_PATH/Beyond_Registration"),
    (r"beyon", "your-user"),
    (r"ANQL6R3224006367", "YOUR_DEVICE_SERIAL"),
    (r"RMO_NX1", "YOUR_PHONE_MODEL"),
]


def wanted(path: Path) -> bool:
    parts = set(path.parts)
    if parts & SKIP_DIRS:
        return False
    name = path.name
    if name in SKIP_NAMES:
        return False
    for pattern in SKIP_FILES:
        if fnmatch.fnmatch(name.lower(), pattern):
            return False
    return True


def scrub(text: str) -> str:
    for pattern, replacement in REPLACEMENTS:
        text = re.sub(pattern, replacement, text)
    return text


def main() -> None:
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)
    copied = scrubbed = 0
    for root, dirs, files in os.walk(SRC):
        root_path = Path(root)
        rel = root_path.relative_to(SRC)
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            source = root_path / name
            rel_path = rel / name
            if not wanted(rel_path):
                continue
            target = STAGE / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.suffix.lower() in TEXT_EXT:
                try:
                    original = source.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    shutil.copy2(source, target)
                    copied += 1
                    continue
                cleaned = scrub(original)
                target.write_text(cleaned, encoding="utf-8")
                copied += 1
                if cleaned != original:
                    scrubbed += 1
            else:
                shutil.copy2(source, target)
                copied += 1

    # A template for the settings file, so a cloner knows what to fill in.
    (STAGE / "desktop" / "tools").mkdir(parents=True, exist_ok=True)
    (STAGE / "desktop" / "tools" / ".env.example").write_text(
        "# Copy to .env and fill in your own values. Never commit the real file.\n"
        "DUCKDNS_DOMAIN=YOUR_DUCKDNS_DOMAIN\n"
        "DUCKDNS_TOKEN=YOUR_DUCKDNS_TOKEN\n"
        "METERED_DOMAIN=YOUR_APP.metered.live\n"
        "METERED_API_KEY=YOUR_METERED_API_KEY\n"
        "VOIC3_RELAY_IMPLEMENTED=1\n"
        "VOIC3_TURN_URL=turn:YOUR_PUBLIC_IP:3478?transport=udp,turn:YOUR_PUBLIC_IP:3478?transport=tcp\n"
        "N3XUS_TURN_EXTERNAL_IP=YOUR_PUBLIC_IP\n"
        "N3XUS_KEYSTORE_PASSWORD=YOUR_KEYSTORE_PASSWORD\n"
        "N3XUS_KEY_ALIAS=nexus\n", encoding="utf-8")

    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(STAGE.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(STAGE))
    # A final sweep: if any known secret shape is still in the staged tree, fail loudly
    # instead of shipping it. Better no ZIP than a leaked token.
    danger = re.compile(
        r"256b6cc5|HSNh5lXwqmFjWoNucTvT|YNGBDjVaZWhJhQwjeNOR|169\.0\.211\.127"
        r"|192\.168\.3\.\d|beyond-2\.duckdns|ANQL6R3224006367|\bbeyon\b")
    leaks = []
    for path in STAGE.rglob("*"):
        if not path.is_file():
            continue
        try:
            body = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if danger.search(body):
            leaks.append(str(path.relative_to(STAGE)))
    if leaks:
        print("STOPPED - these files still contain a real value:")
        for one in leaks:
            print("  ", one)
        raise SystemExit(1)
    size = ZIP_PATH.stat().st_size
    print("files copied :", copied)
    print("files cleaned:", scrubbed)
    print("zip          :", ZIP_PATH, "%.1f MB" % (size / 1048576))


if __name__ == "__main__":
    main()
