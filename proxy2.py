# -*- coding: utf-8 -*-
import sys
import os
import socket
import ssl
import select
import httplib
import base64
import urlparse
import threading
import gzip
import zlib
import time
import json
import re
import traceback
from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
from SocketServer import ThreadingMixIn
from cStringIO import StringIO
from subprocess import Popen, PIPE
from HTMLParser import HTMLParser
from multiprocessing import Process
import multiprocessing
import database
from database import User

route_table = {
    20000: 'ca.smartproxy.com:20000:rycao18:Unknown',
    20001: 'us.smartproxy.com:10000:rycao18:Unknown',
    20002: 'ca.smartproxy.com:20000:rycao18:Unknown',
    20003: 'us.smartproxy.com:10000:rycao18:Unknown',
    20004: 'ca.smartproxy.com:20000:rycao18:Unknown',
    20005: 'us.smartproxy.com:10000:rycao18:Unknown',
    20006: 'ca.smartproxy.com:20000:rycao18:Unknown',
    20007: 'us.smartproxy.com:10000:rycao18:Unknown',
    20008: 'ca.smartproxy.com:20000:rycao18:Unknown',
    20009: 'us.smartproxy.com:10000:rycao18:Unknown',
    20010: 'ca.smartproxy.com:20000:rycao18:Unknown',
    20011: 'us.smartproxy.com:10000:rycao18:Unknown',
    20012: "proxy.spider.com:8080:berkeley-Unknown-country-us:Rycaorec"
}

mysession = {
    'table': route_table,
    'test': 'test'
}


def with_color(c, s):
    return "\x1b[%dm%s\x1b[0m" % (c, s)


def join_with_script_dir(path):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), path)


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    address_family = socket.AF_INET
    daemon_threads = True

    def handle_error(self, request, client_address):
        # surpress socket/ssl related errors
        cls, e = sys.exc_info()[:2]
        if cls is socket.error or cls is ssl.SSLError:
            pass
        else:
            return HTTPServer.handle_error(self, request, client_address)


class ProxyRequestHandler(BaseHTTPRequestHandler):
    cakey = join_with_script_dir('ca.key')
    cacert = join_with_script_dir('ca.crt')
    # cakey = join_with_script_dir('privkey.pem')
    # cacert = join_with_script_dir('fullchain.pem')

    certkey = join_with_script_dir('cert.key')
    certdir = join_with_script_dir('certs/')
    timeout = 30
    lock = threading.Lock()
    process_lock = None
    ScopedSession = None
    proxy_ip, proxy_port, proxy_username, proxy_password = ('', '', '', '')

    def __init__(self, *args, **kwargs):
        self.tls = threading.local()
        self.tls.conns = {}
        self.username = None
        BaseHTTPRequestHandler.__init__(self, *args, **kwargs)
        # self.proxy_host = "ca.smartproxy.com"
        # self.proxy_port = 20000
        # self.proxy_username = 'rycao18'
        # self.proxy_password = 'Unknown'

    def log_error(self, format, *args):
        # surpress "Request timed out: timeout('timed out',)"
        if isinstance(args[0], socket.timeout):
            return

        self.log_message(format, *args)

    def do_AUTHHEAD(self):
        print("send header")
        self.send_response(407)
        self.send_header('Proxy-Authenticate', 'Basic realm=\"Test\"')
        self.send_header('Content-type', 'text/html')
        self.end_headers()

    def do_Authentication(self, auth_header, session):
        print(auth_header)
        self.user = None
        auth_values = auth_header.split(' ')
        if auth_values[0] != 'Basic':
            return False
        auth_key = auth_values[1]
        username, pwd = base64.decodestring(auth_key).split(':')
        user = session.query(User).filter(User.username == username, User.password == pwd).first()
        print(user)
        self.user = user
        if user is None:
            return False
        return True

    def init_ProxyInfo(self):
        port_number = self.server.server_port
        proxy_parts = route_table[port_number].split(':')
        print(proxy_parts)
        self.proxy_ip = str(proxy_parts[0])
        self.proxy_port = int(proxy_parts[1])
        self.proxy_username = str(proxy_parts[2])
        self.proxy_password = str(proxy_parts[3])

    def do_CONNECT(self):
        self.init_ProxyInfo()
        print("DO CONNECT Proxy Authorization Headers ", self.headers.getheader('Proxy-Authorization'))
        session = self.ScopedSession()
        if self.headers.getheader('Proxy-Authorization') is None:
            self.do_AUTHHEAD()
            self.wfile.write('no auth header received')
            self.wfile.write('\r\n\r\n')
            self.wfile.flush()
            return
        elif not self.do_Authentication(self.headers.getheader('Proxy-Authorization'), session):
            self.do_AUTHHEAD()
            self.wfile.write(self.headers.getheader('Proxy-Authorization'))
            self.wfile.write('Not Authenticated')
            self.wfile.write('\r\n\r\n')
            self.wfile.flush()
            self.ScopedSession.remove()
            return
        # self.ScopedSession.remove()
        if os.path.isfile(self.cakey) and os.path.isfile(self.cacert) and os.path.isfile(self.certkey) and os.path.isdir(self.certdir):
            self.connect_intercept()
        else:
            self.connect_relay()

    def connect_intercept(self):
        hostname = self.path.split(':')[0]
        certpath = "%s/%s.crt" % (self.certdir.rstrip('/'), hostname)

        # with self.lock:
        #     if not os.path.isfile(certpath):
        #         epoch = "%d" % (time.time() * 1000)
        #         p1 = Popen(["openssl", "req", "-new", "-key", self.certkey, "-subj", "/CN=%s" % hostname], stdout=PIPE)
        #         p2 = Popen(["openssl", "x509", "-req", "-days", "3650", "-CA", self.cacert, "-CAkey", self.cakey, "-set_serial", epoch, "-out", certpath], stdin=p1.stdout, stderr=PIPE)
        #         p2.communicate()

        self.wfile.write("%s %d %s\r\n" % (self.protocol_version, 200, 'Connection Established'))
        self.end_headers()

        # self.connection = ssl.wrap_socket(self.connection, keyfile=self.certkey, certfile=certpath, server_side=True)
        self.connection = ssl.wrap_socket(self.connection, keyfile=self.cakey, certfile=self.cacert, server_side=True)
        self.rfile = self.connection.makefile("rb", self.rbufsize)
        self.wfile = self.connection.makefile("wb", self.wbufsize)

        conntype = self.headers.get('Proxy-Connection', '')

        if self.protocol_version == "HTTP/1.1" and conntype.lower() != 'close':
            self.close_connection = 0
        else:
            self.close_connection = 1

    def connect_relay(self):
        session = self.ScopedSession()
        address = self.path.split(':', 1)
        address[1] = int(address[1]) or 443
        auth = '%s:%s' % (self.proxy_username, self.proxy_password)
        self.headers['Proxy-Authorization'] = 'Basic ' + base64.b64encode(auth)
        raw_data = self.raw_requestline + str(self.headers) + "\r\n"
        print(raw_data)
        try:
            address = (self.proxy_ip,self.proxy_port)
            s = socket.create_connection(address, timeout=self.timeout)
            s.sendall(raw_data)
            result = s.recv(8192)
            self.connection.sendall(result)
        except Exception as e:
            self.send_error(502)
            return
        # self.send_response(200, 'Connection Established')
        # self.end_headers()

        conns = [self.connection, s]
        self.close_connection = 0
        streamed_bytes = 0
        while not self.close_connection:
            rlist, wlist, xlist = select.select(conns, [], conns, self.timeout)
            if xlist or not rlist:
                break
            for r in rlist:
                other = conns[1] if r is conns[0] else conns[0]
                data = r.recv(8192)
                streamed_bytes += len(data)

                if not data:
                    self.close_connection = 1
                    break
                other.sendall(data)
        with self.lock:
            if self.user:
                print("=final")
                print(streamed_bytes)
                session.query(User).filter(User.username == self.user.username).update(
                    {User.data_usage: User.data_usage + streamed_bytes})
                session.commit()
        self.ScopedSession.remove()

    def end_handle_request(self):
        self.close_connection = 1
        self.ScopedSession.remove()

    def do_GET(self):
        self.init_ProxyInfo()
        print("========= Do Get Authorization Headers ============", self.headers.getheader('Proxy-Authorization'))
        print(self.path)
        if self.path == 'http://proxy2.test/':
            self.send_cacert()
            return
        print(self.ScopedSession)
        session = self.ScopedSession()

        if not isinstance(self.connection, ssl.SSLSocket):
            # Proxy Authentication Part
            if self.headers.getheader('Proxy-Authorization') is None:
                self.do_AUTHHEAD()
                self.wfile.write('no auth header received')
                self.wfile.flush()
                self.end_handle_request()
                return
            elif not self.do_Authentication(self.headers.getheader('Proxy-Authorization'), session):
                self.do_AUTHHEAD()
                self.wfile.write(self.headers.getheader('Proxy-Authorization'))
                self.wfile.write('Not Authenticated')
                self.wfile.flush()
                self.end_handle_request()
                return

        req = self

        content_length = int(req.headers.get('Content-Length', 0))
        req_body = self.rfile.read(content_length) if content_length else None

        if req.path[0] == '/':
            if isinstance(self.connection, ssl.SSLSocket):
                req.path = "https://%s%s" % (req.headers['Host'], req.path)
            else:
                req.path = "http://%s%s" % (req.headers['Host'], req.path)

        req_body_modified = self.request_handler(req, req_body)
        if req_body_modified is False:
            self.send_error(403)
            self.end_handle_request()
            return
        elif req_body_modified is not None:
            req_body = req_body_modified
            req.headers['Content-length'] = str(len(req_body))

        u = urlparse.urlsplit(req.path)
        scheme, netloc, path = u.scheme, u.netloc, (u.path + '?' + u.query if u.query else u.path)
        assert scheme in ('http', 'https')
        if netloc:
            req.headers['Host'] = netloc
        setattr(req, 'headers', self.filter_headers(req.headers))
        try:
            origin = (scheme, netloc)
            auth = '%s:%s' % (self.proxy_username, self.proxy_password)
            req.headers['Proxy-Authorization'] = 'Basic ' + base64.b64encode(auth)
            if not origin in self.tls.conns:
                if scheme == 'https':
                    self.tls.conns[origin] = httplib.HTTPSConnection(self.proxy_ip, self.proxy_port, timeout=self.timeout)
                    self.tls.conns[origin].set_tunnel(netloc, headers={'Proxy-Authorization': req.headers['Proxy-Authorization']})
                    # self.tls.conns[origin] = httplib.HTTPSConnection(netloc, timeout=self.timeout)
                else:
                    self.tls.conns[origin] = httplib.HTTPConnection(self.proxy_ip, self.proxy_port, timeout=self.timeout)
                    # self.tls.conns[origin].set_tunnel(netloc,headers={'Proxy-Authorization':req.headers['Proxy-Authorization']});
                    # self.tls.conns[origin] = httplib.HTTPConnection(netloc, timeout=self.timeout)
            conn = self.tls.conns[origin]
            if scheme == 'https':
                conn.request(self.command, path, req_body, dict(req.headers))
            else:
                conn.request(self.command, req.path, req_body, dict(req.headers))
            res = conn.getresponse()
            version_table = {10: 'HTTP/1.0', 11: 'HTTP/1.1'}
            setattr(res, 'headers', res.msg)
            setattr(res, 'response_version', version_table[res.version])

            # support streaming
            if not 'Content-Length' in res.headers and 'no-store' in res.headers.get('Cache-Control', ''):
                self.response_handler(req, req_body, res, '')
                setattr(res, 'headers', self.filter_headers(res.headers))
                streamed_bytes = self.relay_streaming(res)
                with self.lock:
                    if self.user:
                        self.user.data_usage = self.user.data_usage + streamed_bytes
                        session.commit()
                    self.save_handler(req, req_body, res, '')
                self.end_handle_request()
                return

            res_body = res.read()
        except Exception as e:
            if origin in self.tls.conns:
                del self.tls.conns[origin]
            self.send_error(502)
            # self.close_connection = 1
            traceback.print_exc()
            self.end_handle_request()
            return

        content_encoding = res.headers.get('Content-Encoding', 'identity')
        res_body_plain = self.decode_content_body(res_body, content_encoding)

        res_body_modified = self.response_handler(req, req_body, res, res_body_plain)
        if res_body_modified is False:
            self.send_error(403)
            # self.close_connection = 1
            self.end_handle_request()
            return
        elif res_body_modified is not None:
            res_body_plain = res_body_modified
            res_body = self.encode_content_body(res_body_plain, content_encoding)
            res.headers['Content-Length'] = str(len(res_body))

        setattr(res, 'headers', self.filter_headers(res.headers))

        self.wfile.write("%s %d %s\r\n" % (self.protocol_version, res.status, res.reason))
        for line in res.headers.headers:
            self.wfile.write(line)
        self.end_headers()
        self.wfile.write(res_body)
        self.wfile.flush()

        with self.lock:
            # print("=============user===========")
            # print(self.user)
            # print(len(res_body))
            if self.user:
                # print("===== add the data usage data")
                # print(self.user.data_usage)
                session.query(User).filter(User.username == self.user.username).update(
                    {User.data_usage: User.data_usage + len(res_body)})

                # self.user.data_usage = self.user.data_usage + len(res_body)
                # print(self.user.data_usage)
                session.commit()
            self.save_handler(req, req_body, res, res_body_plain)
        print("===========Do Get End Response==========")
        self.end_handle_request()

    def relay_streaming(self, res):
        streamed_bytes = 0
        self.wfile.write("%s %d %s\r\n" % (self.protocol_version, res.status, res.reason))
        for line in res.headers.headers:
            self.wfile.write(line)
        self.end_headers()

        try:
            while True:
                chunk = res.read(8192)
                if not chunk:
                    break
                streamed_bytes = streamed_bytes + len(chunk)
                self.wfile.write(chunk)
            self.wfile.flush()
        except socket.error:
            # connection closed by client
            pass
        return streamed_bytes

    do_HEAD = do_GET
    do_POST = do_GET
    do_PUT = do_GET
    do_DELETE = do_GET
    do_OPTIONS = do_GET

    def filter_headers(self, headers):
        # http://tools.ietf.org/html/rfc2616#section-13.5.1
        hop_by_hop = ('connection', 'keep-alive', 'proxy-authenticate',
                      'proxy-authorization', 'te', 'trailers', 'transfer-encoding', 'upgrade')
        for k in hop_by_hop:
            del headers[k]

        # accept only supported encodings
        if 'Accept-Encoding' in headers:
            ae = headers['Accept-Encoding']
            filtered_encodings = [x for x in re.split(r',\s*', ae) if x in ('identity', 'gzip', 'x-gzip', 'deflate')]
            headers['Accept-Encoding'] = ', '.join(filtered_encodings)

        return headers

    def encode_content_body(self, text, encoding):
        if encoding == 'identity':
            data = text
        elif encoding in ('gzip', 'x-gzip'):
            io = StringIO()
            with gzip.GzipFile(fileobj=io, mode='wb') as f:
                f.write(text)
            data = io.getvalue()
        elif encoding == 'deflate':
            data = zlib.compress(text)
        else:
            raise Exception("Unknown Content-Encoding: %s" % encoding)
        return data

    def decode_content_body(self, data, encoding):
        if encoding == 'identity':
            text = data
        elif encoding in ('gzip', 'x-gzip'):
            io = StringIO(data)
            with gzip.GzipFile(fileobj=io) as f:
                text = f.read()
        elif encoding == 'deflate':
            try:
                text = zlib.decompress(data)
            except zlib.error:
                text = zlib.decompress(data, -zlib.MAX_WBITS)
        else:
            raise Exception("Unknown Content-Encoding: %s" % encoding)
        return text

    def send_cacert(self):
        with open(self.cacert, 'rb') as f:
            data = f.read()

        self.wfile.write("%s %d %s\r\n" % (self.protocol_version, 200, 'OK'))
        self.send_header('Content-Type', 'application/x-x509-ca-cert')
        self.send_header('Content-Length', len(data))
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(data)

    def print_info(self, req, req_body, res, res_body):
        return

        def parse_qsl(s):
            return '\n'.join("%-20s %s" % (k, v) for k, v in urlparse.parse_qsl(s, keep_blank_values=True))

        req_header_text = "%s %s %s\n%s" % (req.command, req.path, req.request_version, req.headers)
        res_header_text = "%s %d %s\n%s" % (res.response_version, res.status, res.reason, res.headers)

        print with_color(33, req_header_text)

        u = urlparse.urlsplit(req.path)
        if u.query:
            query_text = parse_qsl(u.query)
            print with_color(32, "==== QUERY PARAMETERS ====\n%s\n" % query_text)

        cookie = req.headers.get('Cookie', '')
        if cookie:
            cookie = parse_qsl(re.sub(r';\s*', '&', cookie))
            print with_color(32, "==== COOKIE ====\n%s\n" % cookie)

        auth = req.headers.get('Authorization', '')
        if auth.lower().startswith('basic'):
            token = auth.split()[1].decode('base64')
            print with_color(31, "==== BASIC AUTH ====\n%s\n" % token)

        if req_body is not None:
            req_body_text = None
            content_type = req.headers.get('Content-Type', '')

            if content_type.startswith('application/x-www-form-urlencoded'):
                req_body_text = parse_qsl(req_body)
            elif content_type.startswith('application/json'):
                try:
                    json_obj = json.loads(req_body)
                    json_str = json.dumps(json_obj, indent=2)
                    if json_str.count('\n') < 50:
                        req_body_text = json_str
                    else:
                        lines = json_str.splitlines()
                        req_body_text = "%s\n(%d lines)" % ('\n'.join(lines[:50]), len(lines))
                except ValueError:
                    req_body_text = req_body
            elif len(req_body) < 1024:
                req_body_text = req_body

            if req_body_text:
                print with_color(32, "==== REQUEST BODY ====\n%s\n" % req_body_text)

        print with_color(36, res_header_text)

        cookies = res.headers.getheaders('Set-Cookie')
        if cookies:
            cookies = '\n'.join(cookies)
            print with_color(31, "==== SET-COOKIE ====\n%s\n" % cookies)

        if res_body is not None:
            res_body_text = None
            content_type = res.headers.get('Content-Type', '')

            if content_type.startswith('application/json'):
                try:
                    json_obj = json.loads(res_body)
                    json_str = json.dumps(json_obj, indent=2)
                    if json_str.count('\n') < 50:
                        res_body_text = json_str
                    else:
                        lines = json_str.splitlines()
                        res_body_text = "%s\n(%d lines)" % ('\n'.join(lines[:50]), len(lines))
                except ValueError:
                    res_body_text = res_body
            elif content_type.startswith('text/html'):
                m = re.search(r'<title[^>]*>\s*([^<]+?)\s*</title>', res_body, re.I)
                if m:
                    h = HTMLParser()
                    print with_color(32, "==== HTML TITLE ====\n%s\n" % h.unescape(m.group(1).decode('utf-8')))
            elif content_type.startswith('text/') and len(res_body) < 1024:
                res_body_text = res_body

            if res_body_text:
                print with_color(32, "==== RESPONSE BODY ====\n%s\n" % res_body_text)

    def request_handler(self, req, req_body):
        pass

    def response_handler(self, req, req_body, res, res_body):
        pass

    def save_handler(self, req, req_body, res, res_body):
        self.print_info(req, req_body, res, res_body)


def test(HandlerClass=ProxyRequestHandler, ServerClass=ThreadingHTTPServer, protocol="HTTP/1.1"):
    if sys.argv[1:]:
        port = int(sys.argv[1])
    else:
        port = 8080
    server_address = ('', port)

    HandlerClass.protocol_version = protocol
    httpd = ServerClass(server_address, HandlerClass)

    sa = httpd.socket.getsockname()
    print "Serving HTTP Proxy on", sa[0], "port", sa[1], "..."
    httpd.serve_forever()


def run_server(port, lock, database_url, HandlerClass=ProxyRequestHandler, ServerClass=ThreadingHTTPServer, protocol="HTTP/1.1", ):
    scoped_session = None
    try:
        server_address = ('', port)
        HandlerClass.protocol_version = protocol
        status, ret_scoped_session = database.init(database_url)
        if not status:
            return
        scoped_session = ret_scoped_session
        HandlerClass.ScopedSession = ret_scoped_session
        HandlerClass.process_lock = lock
        httpd = ServerClass(server_address, HandlerClass)
        sa = httpd.socket.getsockname()
        lock.acquire()
        print "Serving HTTP Proxy on", sa[0], "port", sa[1], "...", '\n'
        lock.release()
        httpd.serve_forever()
        database.session.close()
    except Exception as e:
        lock.acquire()
        print(e)
        lock.release()
        traceback.print_exc()


def RunMultiProcess():
    global route_table, mysession
    init_json = None

    try:
        with open('init.json', 'r') as f:
            init_json = json.load(f)
    except Exception as e:
        print("Loading Init Data Failed")
        print(e)
    else:
        database_url = init_json['DataBaseUrl']
        status, ret_scoped_session = database.init(database_url)
        if not status:
            return
        ret_scoped_session.remove()
        l = multiprocessing.Lock()
        process = []
        for port in init_json['RouteTable']:
            route_table[int(port)] = init_json['RouteTable'][port]
            p = Process(target=run_server, args=(int(port), l, database_url))
            process.append(p)
            p.start()
        for p in process:
            p.join()

        # p = Process(target=run_server, args=(20000, l))
        # p.start()

        # p1 = Process(target=run_server, args=(20001, l))
        # p1.start()

        # p2 = Process(target=run_server, args=(20002, l))
        # p2.start()

        # p3 = Process(target=run_server, args=(20003, l))
        # p3.start()

        # p4 = Process(target=run_server, args=(20004, l))
        # p4.start()

        # p5 = Process(target=run_server, args=(20005, l))
        # p5.start()

        # p6 = Process(target=run_server, args=(20006, l))
        # p6.start()

        # p7 = Process(target=run_server, args=(20007, l))
        # p7.start()

        # p8 = Process(target=run_server, args=(20008, l))
        # p8.start()

        # p9 = Process(target=run_server, args=(20009, l))
        # p9.start()

        # p10 = Process(target=run_server, args=(20010, l))
        # p10.start()


if __name__ == '__main__':
    # test()
    RunMultiProcess()

    # if sys.argv[1:]:
    #     port = int(sys.argv[1])
    # else:
    #     port = 8080
    # l = multiprocessing.Lock()
    # run_server(port, l, "sqlite:///D:\\DOWNLOAD\\Employers\\Richard\\proxy-admin\\proxyAdmin\\db.sqlite3" )
    # run_server(port = 20001)
