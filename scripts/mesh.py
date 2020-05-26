#!/usr/bin/env python3

import pandas as pd
import subprocess
import json
import base58
import base64
import sys
import itertools

# FIXME - don't hardcode
TRACE_ARCHIVE = 'output/mesh-test/analysis/filtered-trace.bin.gz'

TYPE_GRAFT = 11
TYPE_PRUNE = 12


def trace_event_stream(trace_filename):
    """
    Convert the trace events in trace_filename to python dicts (via json)
    :param trace_filename: gzipped file of protobuf trace events
    :return: a generator that yields a dictionary representation of each event.
    """
    cmd = ['go', 'run', 'github.com/libp2p/go-libp2p-pubsub-tracer/cmd/trace2json', trace_filename]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, universal_newlines=True)
    for line in p.stdout:
        yield json.loads(line)


def mesh_trace_event_stream(trace_filename):
    """
    Converts the trace events in trace_filename to python dicts, filtering out
    everything except GRAFT / PRUNE events.
    :param trace_filename: gzipped file of protobuf trace events
    :return: a generator that yields a dictionary representation of each event.
    """
    for event in trace_event_stream(trace_filename):
        typ = event.get('type', -1)
        if typ == TYPE_GRAFT or typ == TYPE_PRUNE:
            yield event


def empty_mesh_events_table():
    return pd.DataFrame([], columns=['timestamp', 'peer', 'remote_peer', 'graft']).astype({
        'timestamp': 'datetime64[ns]',
        'peer': 'int64',
        'remote_peer': 'int64',
        'graft': 'bool',
    })


def mesh_events_to_pandas(event_stream, peers_table):
    topic_tables = {}

    i = 0
    for evt in event_stream:
        typ = evt.get('type', -1)
        if typ == TYPE_GRAFT:
            info = evt['graft']
        elif typ == TYPE_PRUNE:
            info = evt['prune']
        else:
            print('unexpected event type {}'.format(typ), file=sys.stderr)
            continue

        timestamp = pd.to_datetime(evt['timestamp'])
        topic = info['topic']
        peer = numeric_peer_id(b64_to_b58(evt['peerID']), peers_table)
        remote_peer = numeric_peer_id(b64_to_b58(info['peerID']), peers_table)

        if topic not in topic_tables:
            topic_tables[topic] = empty_mesh_events_table()
        df = topic_tables[topic]

        row = [timestamp, peer, remote_peer, typ == TYPE_GRAFT]
        df.at[i] = row
        i += 1
    df.set_index('timestamp', inplace=True)
    return df.astype({'peer': 'int64', 'remote_peer': 'int64'})


def b64_to_b58(b64_str):
    b = base64.b64decode(b64_str)
    return base58.b58encode(b).decode('utf8')


def numeric_peer_id(pid_str, peers_table):
    return peers_table[['peer_id', 'seq']].where(peers_table['peer_id'] == pid_str).dropna()['seq'].iloc[0]

if __name__ == '__main__':
    events = itertools.islice(mesh_trace_event_stream(TRACE_ARCHIVE), 100)
    peers_table = pd.read_pickle('output/mesh-test/analysis/pandas/peers.gz')
    df = mesh_events_to_pandas(events, peers_table)
    print(df)
