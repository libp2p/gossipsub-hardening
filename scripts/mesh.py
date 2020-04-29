#!/usr/bin/env python3

import pandas as pd
import numpy as np
import subprocess
import json
import base58
import base64
import sys
import itertools
from collections import defaultdict
import pandas_sets # imported for side effects!

from functools import reduce

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
    return pd.DataFrame([], columns=['timestamp', 'peer', 'grafted', 'pruned']).astype({
        'timestamp': 'datetime64[ns]',
        'peer': 'int64',
    }).set_index('timestamp')


def mesh_events_to_pandas(event_stream, peers_table):
    tables = defaultdict(empty_mesh_events_table)
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

        df = tables[peer]

        grafted = set()
        pruned = set()
        if typ == TYPE_GRAFT:
            grafted.add(remote_peer)
        if typ == TYPE_PRUNE:
            pruned.add(remote_peer)
        row = [peer, grafted, pruned]
        df.loc[timestamp] = row

    def set_union(series):
        return reduce(lambda x, y: x.union(y), series, set())

    resampled = []
    sample_freq = '5s'
    for peer, table in tables.items():
        t = table[['grafted', 'pruned']].resample(sample_freq).agg(set_union)
        mesh = set()
        # meshes = pd.Series(index=t.index, dtype='object')
        honest = pd.Series(index=t.index, dtype='int32')
        attacker = pd.Series(index=t.index, dtype='int32')
        for index, row in t.iterrows():
            mesh.update(row['grafted'])
            mesh.difference_update(row['pruned'])
            # meshes[index] = mesh.copy()
            h, a = classify_mesh_peers(mesh, peers_table)
            honest[index] = len(h)
            attacker[index] = len(a)
        # t['mesh'] = meshes
        t['n_mesh_honest'] = honest
        t['n_mesh_attacker'] = attacker
        t['peer'] = peer
        resampled.append(t.drop(columns=['grafted', 'pruned']))

    return pd.concat(resampled)


def b64_to_b58(b64_str):
    b = base64.b64decode(b64_str)
    return base58.b58encode(b).decode('utf8')


def numeric_peer_id(pid_str, peers_table):
    pid = peers_table[['peer_id', 'seq']].where(peers_table['peer_id'] == pid_str).dropna()['seq'].iloc[0]
    return int(pid)

def classify_mesh_peers(mesh, peers_table):
    peers = peers_table.set_index('seq')
    mesh_honest = set()
    mesh_attacker = set()
    for p in mesh:
        try:
            honest = peers.loc[p]['honest']
        except KeyError:
            continue
        if honest:
            mesh_honest.add(p)
        else:
            mesh_attacker.add(p)
    return mesh_honest, mesh_attacker


if __name__ == '__main__':
    events = itertools.islice(mesh_trace_event_stream(TRACE_ARCHIVE), 100)
    peers_table = pd.read_pickle('output/mesh-test/analysis/pandas/peers.gz')
    df = mesh_events_to_pandas(events, peers_table)
    print(df)
