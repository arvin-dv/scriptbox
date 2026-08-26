"""Network diagnostics and HTTP utilities: http, port-scan, trace-url, download."""

import argparse
import hashlib
import json
import socket
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from scriptbox.utils.console import (
    Colors,
    colorize,
    format_bytes,
    format_duration,
    output_json_or_text,
    print_error,
    print_header,
    print_info,
    print_success,
    print_table,
    print_warning,
)


COMMON_PORTS = {
    21: "FTP",
    22: "SSH",
    23: "Telnet",
    25: "SMTP",
    53: "DNS",
    80: "HTTP",
    110: "POP3",
    143: "IMAP",
    443: "HTTPS",
    465: "SMTPS",
    587: "SMTP Submission",
    993: "IMAPS",
    995: "POP3S",
    1433: "MSSQL",
    1521: "Oracle",
    3000: "Node/React Dev",
    3306: "MySQL/MariaDB",
    5000: "Flask/Dev",
    5432: "PostgreSQL",
    6379: "Redis",
    8000: "HTTP-Alt / Django",
    8080: "HTTP-Proxy / Tomcat",
    8443: "HTTPS-Alt",
    9200: "Elasticsearch",
    27017: "MongoDB",
}


def register_subcommands(subparsers: argparse._SubParsersAction) -> None:
    """Register network tool subcommands."""

    # 1. http
    p_http = subparsers.add_parser(
        "http",
        help="Make HTTP requests with response timing, header inspection, and body formatting.",
        description="Lightweight HTTP client with latency measurement, header inspection, and SSL checks.",
    )
    p_http.add_argument("url", help="Target URL (e.g. https://httpbin.org/get).")
    p_http.add_argument("-X", "--method", default="GET", help="HTTP Method (GET, POST, PUT, DELETE, HEAD).")
    p_http.add_argument("-H", "--header", action="append", dest="headers", help="HTTP Request Header (e.g. -H 'Authorization: Bearer xyz').")
    p_http.add_argument("-d", "--data", help="Request body data.")
    p_http.add_argument("-i", "--include-headers", action="store_true", help="Display response headers in output.")
    p_http.add_argument("--timeout", type=float, default=10.0, help="Request timeout in seconds (default: 10).")
    p_http.add_argument("--json", action="store_true", help="Output complete response details as JSON.")
    p_http.set_defaults(func=cmd_http)

    # 2. port-scan
    p_scan = subparsers.add_parser(
        "port-scan",
        help="Fast multithreaded TCP port scanner for host discovery.",
        description="Scan network hosts for open TCP ports and identify services.",
    )
    p_scan.add_argument("host", help="Target host IP or domain name (e.g. 127.0.0.1, localhost).")
    p_scan.add_argument("-p", "--ports", help="Port range or comma-separated list (e.g. 80,443 or 1-1024). Default: common services.")
    p_scan.add_argument("-t", "--threads", type=int, default=50, help="Concurrent worker threads (default: 50).")
    p_scan.add_argument("--timeout", type=float, default=1.0, help="Socket timeout in seconds (default: 1.0).")
    p_scan.add_argument("--json", action="store_true", help="Output scan results as JSON.")
    p_scan.set_defaults(func=cmd_port_scan)

    # 3. trace-url
    p_trace = subparsers.add_parser(
        "trace-url",
        help="Trace HTTP/HTTPS redirect chains and inspect status codes at each hop.",
        description="Follow redirect chains (301, 302, 307, 308) to discover the final destination URL.",
    )
    p_trace.add_argument("url", help="Initial URL to trace.")
    p_trace.add_argument("--max-hops", type=int, default=15, help="Maximum number of redirects to follow (default: 15).")
    p_trace.add_argument("--json", action="store_true", help="Output redirect hops as JSON.")
    p_trace.set_defaults(func=cmd_trace_url)

    # 4. download
    p_dl = subparsers.add_parser(
        "download",
        help="Download files with real-time progress bar and checksum validation.",
        description="Resilient file downloader supporting custom output paths and SHA256 integrity checks.",
    )
    p_dl.add_argument("url", help="File URL to download.")
    p_dl.add_argument("-o", "--output", help="Destination file path (defaults to remote filename).")
    p_dl.add_argument("--sha256", help="Expected SHA256 hash to verify file integrity upon completion.")
    p_dl.set_defaults(func=cmd_download)


def cmd_http(args: argparse.Namespace) -> int:
    """Execute HTTP request."""
    url = args.url
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    headers = {"User-Agent": "scriptbox-cli/0.1.0"}
    if args.headers:
        for h in args.headers:
            if ":" in h:
                k, v = h.split(":", 1)
                headers[k.strip()] = v.strip()

    data_bytes = args.data.encode("utf-8") if args.data else None
    req = urllib.request.Request(url, data=data_bytes, headers=headers, method=args.method.upper())

    start_time = time.time()
    try:
        with urllib.request.urlopen(req, timeout=args.timeout) as resp:
            elapsed = time.time() - start_time
            body_bytes = resp.read()
            status_code = resp.status
            resp_headers = dict(resp.headers)
    except urllib.error.HTTPError as e:
        elapsed = time.time() - start_time
        body_bytes = e.read()
        status_code = e.code
        resp_headers = dict(e.headers)
    except Exception as e:
        print_error(f"HTTP request error: {e}")
        return 1

    try:
        body_text = body_bytes.decode("utf-8")
    except UnicodeDecodeError:
        body_text = f"<Binary data: {len(body_bytes)} bytes>"

    if args.json:
        result = {
            "url": url,
            "status_code": status_code,
            "duration_seconds": elapsed,
            "headers": resp_headers,
            "body": body_text,
        }
        output_json_or_text(result, as_json=True)
        return 0

    # Colorize status code
    status_color = Colors.GREEN if status_code < 300 else Colors.YELLOW if status_code < 400 else Colors.RED
    print(colorize(f"HTTP/{args.method.upper()} {url} -> {status_code} ({format_duration(elapsed)})", status_color))

    if args.include_headers:
        print_header("Response Headers")
        for k, v in resp_headers.items():
            print(f"  {colorize(k, Colors.CYAN)}: {v}")
        print()

    # Pretty print body if JSON
    try:
        parsed = json.loads(body_text)
        print(json.dumps(parsed, indent=2))
    except Exception:
        print(body_text)

    return 0 if status_code < 400 else 1


def check_port(host: str, port: int, timeout: float) -> Optional[Dict[str, Any]]:
    """Probe a single TCP port."""
    start = time.time()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            if s.connect_ex((host, port)) == 0:
                elapsed = (time.time() - start) * 1000
                service = COMMON_PORTS.get(port, "Unknown")
                return {"port": port, "service": service, "latency_ms": elapsed}
    except Exception:
        pass
    return None


def cmd_port_scan(args: argparse.Namespace) -> int:
    """Execute multithreaded port scanner."""
    host = args.host
    try:
        ip = socket.gethostbyname(host)
    except socket.gaierror as e:
        print_error(f"Cannot resolve host '{host}': {e}")
        return 1

    ports_to_scan: List[int] = []
    if args.ports:
        for part in args.ports.split(","):
            part = part.strip()
            if "-" in part:
                start_p, end_p = map(int, part.split("-"))
                ports_to_scan.extend(range(start_p, end_p + 1))
            elif part.isdigit():
                ports_to_scan.append(int(part))
    else:
        ports_to_scan = sorted(COMMON_PORTS.keys())

    if not args.json:
        print_info(f"Scanning {host} ({ip}) across {len(ports_to_scan)} port(s)...")

    open_ports: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=args.threads) as executor:
        futures = {executor.submit(check_port, ip, p, args.timeout): p for p in ports_to_scan}
        for fut in as_completed(futures):
            res = fut.result()
            if res:
                open_ports.append(res)

    open_ports.sort(key=lambda x: x["port"])

    if args.json:
        output_json_or_text({"host": host, "ip": ip, "open_ports": open_ports}, as_json=True)
        return 0

    if open_ports:
        print_header(f"Open Ports on {host} ({ip}) - {len(open_ports)} found")
        rows = [
            [str(p["port"]), p["service"], f"{p['latency_ms']:.1f} ms"]
            for p in open_ports
        ]
        print_table(["Port", "Service", "Latency"], rows)
    else:
        print_info(f"No open ports discovered on {host}.")

    return 0


def cmd_trace_url(args: argparse.Namespace) -> int:
    """Trace HTTP redirect chains."""
    url = args.url
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    hops: List[Dict[str, Any]] = []
    current_url = url

    class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    opener = urllib.request.build_opener(NoRedirectHandler)

    for hop_num in range(1, args.max_hops + 1):
        req = urllib.request.Request(
            current_url,
            headers={"User-Agent": "scriptbox-cli/0.1.0"},
            method="HEAD",
        )
        try:
            with opener.open(req, timeout=10.0) as resp:
                status = resp.status
                hops.append({"hop": hop_num, "status": status, "url": current_url})
                break
        except urllib.error.HTTPError as e:
            status = e.code
            loc = e.headers.get("Location")
            hops.append({"hop": hop_num, "status": status, "url": current_url, "location": loc})
            if loc and status in (301, 302, 303, 307, 308):
                current_url = urllib.parse.urljoin(current_url, loc)
            else:
                break
        except Exception as e:
            print_error(f"Error during trace hop {hop_num}: {e}")
            break

    if args.json:
        output_json_or_text(hops, as_json=True)
        return 0

    print_header(f"Redirect Trace for {url}")
    rows = []
    for h in hops:
        status_str = str(h["status"])
        color = Colors.GREEN if h["status"] < 300 else Colors.YELLOW
        rows.append([str(h["hop"]), colorize(status_str, color), h["url"]])
    print_table(["Hop", "Status", "URL"], rows)

    if hops and hops[-1]["status"] < 300:
        print_success(f"Final Destination: {hops[-1]['url']}")

    return 0


def cmd_download(args: argparse.Namespace) -> int:
    """Download a file with progress and hash validation."""
    url = args.url
    out_path = Path(args.output) if args.output else Path(urllib.parse.urlparse(url).path.split("/")[-1] or "downloaded_file")

    print_info(f"Downloading {url} -> {out_path}...")
    req = urllib.request.Request(url, headers={"User-Agent": "scriptbox-cli/0.1.0"})

    try:
        with urllib.request.urlopen(req, timeout=30.0) as resp:
            total_size = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            hasher = hashlib.sha256()

            with open(out_path, "wb") as f:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    hasher.update(chunk)
                    downloaded += len(chunk)

                    if total_size > 0:
                        pct = downloaded / total_size * 100
                        sys.stdout.write(f"\rProgress: [{pct:5.1f}%] {format_bytes(downloaded)} / {format_bytes(total_size)}")
                        sys.stdout.flush()

            sys.stdout.write("\n")

        computed_sha256 = hasher.hexdigest()
        print_success(f"Downloaded {format_bytes(downloaded)} to {out_path}")
        print_info(f"SHA256: {computed_sha256}")

        if args.sha256:
            if computed_sha256.lower() == args.sha256.lower():
                print_success("SHA256 Checksum verified successfully!")
                return 0
            else:
                print_error(f"SHA256 Mismatch! Expected: {args.sha256}, Got: {computed_sha256}")
                return 1

        return 0
    except Exception as e:
        print_error(f"Download failed: {e}")
        return 1
