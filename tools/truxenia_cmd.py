"""Client for the TruXenia link (tools/truxenia.py): sends one command line to 127.0.0.1:<port> and prints the answer.

Usage (from the repository root):
  ../bin/pyt -t 30 tools/truxenia_cmd.py status
  ../bin/pyt -t 30 tools/truxenia_cmd.py enemies | lara | hits 20 | saves
  ../bin/pyt -t 30 tools/truxenia_cmd.py snapshot ../logs/truxenia/snap.json
  ../bin/pyt -t 30 tools/truxenia_cmd.py watch 120 ../logs/truxenia/fight.tsv
  ../bin/pyt -t 30 tools/truxenia_cmd.py sonar                   PDA sonar values (2026-11-14)
  ../bin/pyt -t 30 tools/truxenia_cmd.py peek 829ca5a4 64        read-only memory view (guest address hex, length)
  ../bin/pyt -t 30 tools/truxenia_cmd.py --port 47011 quit
Every answer is also written to TruXenia's own log. Exit 0 = answer received, 1 = no link.
"""
import socket
import sys

DEFAULT_PORT = 47011


def send(line, port=DEFAULT_PORT, timeout=5.0):
    with socket.create_connection(('127.0.0.1', port), timeout=timeout) as s:
        s.sendall((line.strip() + '\n').encode('utf-8'))
        data = b''
        while not data.endswith(b'\n.\n'):
            chunk = s.recv(65536)
            if not chunk:
                break
            data += chunk
    text = data.decode('utf-8', 'replace')
    if text.endswith('\n.\n'):
        text = text[:-3]
    return text.split('\n') if text else []


def main():
    a = sys.argv[1:]
    port = DEFAULT_PORT
    if len(a) >= 2 and a[0] == '--port':
        port = int(a[1])
        a = a[2:]
    if not a:
        print(__doc__)
        return 2
    try:
        for line in send(' '.join(a), port):
            print(line)
    except OSError as ex:
        print('no TruXenia link on 127.0.0.1:%d (%s)' % (port, ex))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
