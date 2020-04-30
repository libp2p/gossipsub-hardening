package main

import (
	"context"
	"fmt"
	"github.com/multiformats/go-multiaddr"
	manet "github.com/multiformats/go-multiaddr-net"
	"math/rand"
	"net"
	"os"
	"time"

	"github.com/testground/sdk-go/runtime"
	"github.com/testground/sdk-go/sync"
)

// setupNetwork instructs the sidecar (if enabled) to setup the network for this
// test case.
func setupNetwork(ctx context.Context, runenv *runtime.RunEnv, netParams NetworkParams, client *sync.Client) error {
	if !runenv.TestSidecar {
		return nil
	}

	// Wait for the network to be initialized.
	runenv.RecordMessage("Waiting for network initialization")
	if err := client.WaitNetworkInitialized(ctx, runenv); err != nil {
		return err
	}
	runenv.RecordMessage("Network init complete")

	hostname, err := os.Hostname()
	if err != nil {
		return err
	}

	latency := netParams.latency
	if netParams.latencyMax > 0 {
		// If a maximum latency is supplied, choose a random latency between
		// latency and max latency
		latency += time.Duration(rand.Float64() * float64(netParams.latencyMax-latency))
	}

	// random delay to avoid overloading weave (we hope)
	delay := time.Duration(rand.Intn(1000)) * time.Millisecond
	<-time.After(delay)
	_, err = client.Publish(ctx, sync.NetworkTopic(hostname), &sync.NetworkConfig{
		Network: "default",
		Enable:  true,
		Default: sync.LinkShape{
			Latency:   latency,
			Bandwidth: uint64(netParams.bandwidthMB) * 1024 * 1024,
			Jitter:    (time.Duration(netParams.jitterPct) * netParams.latency) / 100,
		},
		State: "network-configured",
	})
	if err != nil {
		return fmt.Errorf("failed to configure network: %w", err)
	}

	runenv.RecordMessage("egress: %s latency (%d%% jitter) and %dMB bandwidth", netParams.latency, netParams.jitterPct, netParams.bandwidthMB)

	err = <-client.MustBarrier(ctx, "network-configured", runenv.TestInstanceCount).C
	if err != nil {
		return fmt.Errorf("failed to configure network: %w", err)
	}
	return nil
}

// getDataNetworkAddress examines the local network interfaces and tries to find one with
// an address inside runenv.TestSubnet. Returns the addr if successful.
func getDataNetworkAddress(runenv *runtime.RunEnv) (multiaddr.Multiaddr, error) {
	// if there's no test sidecar, we're using the local:exec runner and don't care
	// which interface we bind to
	if !runenv.TestSidecar {
		return multiaddr.StringCast("/ip4/0.0.0.0"), nil
	}

	ifaces, err := net.Interfaces()
	if err != nil {
		return nil, fmt.Errorf("unable to get local network interfaces: %s", err)
	}
	for _, i := range ifaces {
		addrs, err := i.Addrs()
		if err != nil {
			runenv.RecordMessage("error getting addrs for interface: %s", err)
			continue
		}
		for _, a := range addrs {
			switch v := a.(type) {
			case *net.IPNet:
				ip := v.IP.To4()
				if ip == nil {
					runenv.RecordMessage("ignoring non ip4 addr %s", v)
					continue
				}
				if runenv.TestSubnet.Contains(ip) {
					runenv.RecordMessage("detected data network IP %s", v)
					return manet.FromIP(v.IP)
				} else {
					runenv.RecordMessage("%s not in data subnet %s, ignoring", ip, runenv.TestSubnet.String())
				}
			}
		}
	}
	return nil, fmt.Errorf("unable to determine data network IP. no interface found with IP in %s", runenv.TestSubnet.String())
}
