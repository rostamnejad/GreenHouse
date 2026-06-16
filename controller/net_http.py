try:
    import usocket as socket
except ImportError:
    import socket

try:
    import ussl as ssl
except ImportError:
    import ssl


DEFAULT_TIMEOUT_SECONDS = 6


class Response:
    def __init__(self, status_code, content):
        self.status_code = status_code
        self.content = content

    def close(self):
        pass


def _parse_url(url):
    scheme_end = url.find("://")
    if scheme_end < 0:
        raise ValueError("URL scheme missing")

    scheme = url[:scheme_end]
    rest = url[scheme_end + 3 :]
    path_start = rest.find("/")
    if path_start < 0:
        host_port = rest
        path = "/"
    else:
        host_port = rest[:path_start]
        path = rest[path_start:]

    if ":" in host_port:
        host, port_text = host_port.rsplit(":", 1)
        port = int(port_text)
    else:
        host = host_port
        port = 443 if scheme == "https" else 80

    if scheme not in ("http", "https"):
        raise ValueError("Unsupported URL scheme: %s" % scheme)

    return scheme, host, port, path


def _wrap_ssl(sock, host):
    if hasattr(ssl, "create_default_context"):
        context = ssl.create_default_context()
        return context.wrap_socket(sock, server_hostname=host)

    try:
        return ssl.wrap_socket(sock, server_hostname=host)
    except TypeError:
        return ssl.wrap_socket(sock)


def _send(sock, data):
    try:
        return sock.write(data)
    except AttributeError:
        try:
            return sock.sendall(data)
        except AttributeError:
            return sock.send(data)


def _recv(sock, size):
    try:
        return sock.read(size)
    except AttributeError:
        return sock.recv(size)


def _status_code(header):
    first_line = header.split(b"\r\n", 1)[0]
    if not first_line:
        first_line = header.split(b"\n", 1)[0]
    parts = first_line.split()
    if len(parts) < 2:
        return 0
    try:
        return int(parts[1])
    except Exception:
        return 0


def get(url, headers=None, timeout=DEFAULT_TIMEOUT_SECONDS):
    if headers is None:
        headers = {}

    scheme, host, port, path = _parse_url(url)
    stream = getattr(socket, "SOCK_STREAM", 1)
    addr = socket.getaddrinfo(host, port, 0, stream)[0]
    sock = socket.socket(addr[0], addr[1], addr[2])
    sock.settimeout(timeout)

    try:
        sock.connect(addr[-1])
        if scheme == "https":
            sock = _wrap_ssl(sock, host)
            try:
                sock.settimeout(timeout)
            except Exception:
                pass

        request_headers = [
            "GET %s HTTP/1.0" % path,
            "Host: %s" % host,
            "Connection: close",
        ]
        for key, value in headers.items():
            request_headers.append("%s: %s" % (key, value))
        request = "\r\n".join(request_headers) + "\r\n\r\n"
        _send(sock, request.encode())

        chunks = []
        while True:
            chunk = _recv(sock, 1024)
            if not chunk:
                break
            chunks.append(chunk)

        raw = b"".join(chunks)
        split_at = raw.find(b"\r\n\r\n")
        delimiter_size = 4
        if split_at < 0:
            split_at = raw.find(b"\n\n")
            delimiter_size = 2
        if split_at < 0:
            return Response(0, raw)

        header = raw[:split_at]
        body = raw[split_at + delimiter_size :]
        return Response(_status_code(header), body)
    finally:
        try:
            sock.close()
        except Exception:
            pass
