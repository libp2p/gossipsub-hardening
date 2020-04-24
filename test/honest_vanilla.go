// +build !hardened_api

package main

import (
	pubsub "github.com/libp2p/go-libp2p-pubsub"
)

func pubsubOptions(cfg HonestNodeConfig) ([]pubsub.Option, error) {
	opts := []pubsub.Option{
		pubsub.WithEventTracer(cfg.Tracer),
	}

	if cfg.ValidateQueueSize > 0 {
		opts = append(opts, pubsub.WithValidateQueueSize(cfg.ValidateQueueSize))
	}

	if cfg.OutboundQueueSize > 0 {
		opts = append(opts, pubsub.WithPeerOutboundQueueSize(cfg.OutboundQueueSize))
	}

	return opts, nil
}
