package main

import (
	"context"
	"fmt"
	"io"
	"strings"

	ggio "github.com/gogo/protobuf/io"
	"github.com/gogo/protobuf/proto"

	"github.com/libp2p/go-libp2p-core/host"
	"github.com/libp2p/go-libp2p-core/network"
	"github.com/libp2p/go-libp2p-core/peer"
	"github.com/libp2p/go-libp2p-core/protocol"
	pubsub_pb "github.com/libp2p/go-libp2p-pubsub/pb"

	"github.com/testground/sdk-go/runtime"
)

const gossipSubID = protocol.ID("/meshsub/1.0.0")
const maxMessageSize = 1024 * 1024

type pubsubRPC struct {
	pubsub_pb.RPC

	from peer.ID
}

func (rpc pubsubRPC) Description() string {
	return fmt.Sprintf("RPC from %s: \n%s", rpc.from.Pretty(), proto.MarshalTextString(&rpc.RPC))
}

type PubSubSybil struct {
	ctx    context.Context
	h      host.Host
	runenv *runtime.RunEnv
	seq    int64
}

func NewSybil(ctx context.Context, runenv *runtime.RunEnv, h host.Host, seq int64) (*PubSubSybil, error) {
	s := PubSubSybil{
		ctx:    ctx,
		h:      h,
		runenv: runenv,
		seq:    seq,
	}

	h.SetStreamHandler(gossipSubID, s.handlePubsubStream)
	return &s, nil
}

func (s *PubSubSybil) ConnectToPeer(ctx context.Context, info peer.AddrInfo) error {
	return s.h.Connect(ctx, info)
}

func (s *PubSubSybil) log(msg string, args ...interface{}) {
	prefix := fmt.Sprintf("[sybil %d %s] ", s.seq, s.h.ID().Pretty()[:8])
	s.runenv.RecordMessage(prefix+msg, args...)
}

func (s *PubSubSybil) handlePubsubStream(stream network.Stream) {
	s.log("new stream from %s", stream.Conn().RemotePeer().Pretty())
	r := ggio.NewDelimitedReader(stream, maxMessageSize)

	for {
		rpc := new(pubsubRPC)
		err := r.ReadMsg(&rpc.RPC)
		if err != nil {
			if err != io.EOF {
				stream.Reset()
				s.runenv.RecordMessage("error reading rpc from %s: %s", stream.Conn().RemotePeer(), err)
			} else {
				// Just be nice. They probably won't read this
				// but it doesn't hurt to send it.
				stream.Close()
			}
			return
		}

		rpc.from = stream.Conn().RemotePeer()

		response, err := s.handleRPC(rpc)
		if err != nil {
			s.log("error handling RPC: %s", err)
			_ = stream.Close()
		}
		if response == nil {
			continue
		}

		err = s.sendRPC(rpc.from, response)
		if err != nil {
			s.log("error sending RPC: %s", err)
		}
	}
}

// TODO: don't open new stream for every outgoing RPC
func (s *PubSubSybil) sendRPC(p peer.ID, rpc *pubsubRPC) error {
	stream, err := s.h.NewStream(s.ctx, p, gossipSubID)
	if err != nil {
		return err
	}
	w := ggio.NewDelimitedWriter(stream)
	err = w.WriteMsg(&rpc.RPC)
	if err != nil {
		s.log("error writing RPC message: %s", err)
		_ = stream.Close()
	}
	return nil
}

func (s *PubSubSybil) handleRPC(rpc *pubsubRPC) (*pubsubRPC, error) {
	//s.log("got RPC:\n%s", rpc.Description())

	// always pretend to be subscribed to the same topics as our peers
	// and attempt to graft onto their mesh
	if len(rpc.Subscriptions) != 0 {
		out := new(pubsubRPC)
		out.from = s.h.ID()

		ctrl := pubsub_pb.ControlMessage{}
		var topics []string
		for _, sub := range rpc.Subscriptions {
			topics = append(topics, sub.GetTopicid())
			graft := pubsub_pb.ControlGraft{
				TopicID: sub.Topicid,
			}
			out.Subscriptions = append(out.Subscriptions, sub)
			if *sub.Subscribe {
				ctrl.Graft = append(ctrl.Graft, &graft)
			}
		}

		s.log("grafting onto topics for peer %s: %s", rpc.from.Pretty(), strings.Join(topics, ", "))
		return out, nil
	}

	if len(rpc.Publish) != 0 {
		//s.log("swallowing %d messages from %s", len(rpc.Publish), rpc.from.Pretty())
	}
	return nil, nil
}
