#!/usr/bin/env python3

import pandas as pd
import subprocess
import json
import base58
import base64
import sys
from collections import defaultdict
import pandas_sets # imported for side effects!

from functools import reduce

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
    """
    :return: An empty DataFrame used to collect mesh state for a peer, used by mesh_events_to_pandas.
    """
    return pd.DataFrame([], columns=['timestamp', 'peer', 'grafted', 'pruned']).astype({
        'timestamp': 'datetime64[ns]',
        'peer': 'int64',
    }).set_index('timestamp')


def mesh_events_to_pandas(event_stream, peers_table, sample_freq='5s'):
    """
    Converts a stream of GRAFT / PRUNE tracer events to a pandas dataframe
    containing the state of each peers mesh, sampled at sample_freq intervals.
    """

    # building the mesh state is simpler if we have one DataFrame per peer
    # and concat them together at the end.
    tables = defaultdict(empty_mesh_events_table)

    # first we build up a table of grafts / prunes. The 'grafted' and 'pruned' columns
    # contain python set objects with the seq id of the grafted or pruned peer.
    # These sets are used below to derive the mesh state.
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
        topic = info['topic']  # TODO: multiple topics
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

    # reducer to return the union of all sets in a column, used when resampling
    def set_union(series):
        return reduce(lambda x, y: x.union(y), series, set())

    resampled = []
    for peer, table in tables.items():
        # resample the raw grafts / prunes into windows of 5 secs (by default)
        # the 'grafted' and 'pruned' columns for each window will contain the
        # union of all peers grafted or pruned within the window
        t = table[['grafted', 'pruned']].resample(sample_freq).agg(set_union)

        # we collect the mesh state here by iterating over the resampled table applying the grafts and prunes
        mesh = set()

        # series objects to contain the mesh state, plus the number of honest / dishonest peers
        # in the mesh for a given time window
        meshes = pd.Series(index=t.index, dtype='object')
        honest = pd.Series(index=t.index, dtype='int16')
        attacker = pd.Series(index=t.index, dtype='int16')
        for index, row in t.iterrows():
            mesh.update(row['grafted'])
            mesh.difference_update(row['pruned'])
            meshes[index] = mesh.copy()
            h, a = classify_mesh_peers(mesh, peers_table)
            honest[index] = len(h)
            attacker[index] = len(a)
        # add the new columns and drop the raw grafted / pruned cols
        t['mesh'] = meshes
        t['n_mesh_honest'] = honest
        t['n_mesh_attacker'] = attacker
        t['peer'] = peer
        resampled.append(t.drop(columns=['grafted', 'pruned']))

    return pd.concat(resampled)


def b64_to_b58(b64_str):
    b = base64.b64decode(b64_str)
    return base58.b58encode(b).decode('utf8')


def numeric_peer_id(pid_str, peers_table):
    """
    Given a base58 peer id string and a table of peer info, returns the numeric seq number
    for the peer.
    """
    pid = peers_table[['peer_id', 'seq']].where(peers_table['peer_id'] == pid_str).dropna()['seq'].iloc[0]
    return int(pid)


def classify_mesh_peers(mesh, peers_table):
    """
    Given a set of peer seq numbers and a table of peer info, returns two sets.
    The first contains honest peers, the second dishonest peers.
    """
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

