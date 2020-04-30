# Shared jupyterhub Workflow

This doc describes how we (the gossipsub-hardening team at Protocol Labs) have been running the tests in this repo.

## Connecting to the Jupyterhub server

We have an EC2 instance running Ubuntu 18.04, with [The Littlest Jupyterhub][tljh] installed. It doesn't
have a persistent domain or SSL cert, so we've been connecting to it using an SSH tunnel.

The current incantation is:

```shell
ssh -A -L 8666:localhost:80 jupyter-protocol@ec2-3-122-216-37.eu-central-1.compute.amazonaws.com
```

This will open a shell as the `jupyter-protocol` user, and tunnel traffic from port 80 on the remote
machine to port 8666 on localhost.

If your ssh key isn't authorized, ping @yusefnapora (or someone else with access, if I'm sleeping or something)
to get added to the `authorized_keys` file.

The `-A` flag enables ssh-agent forwarding, which will let you pull from this repo while you're shelled in, assuming 
your SSH key is linked to your github account & you have read access to this repo. Note that the agent forwarding
doesn't seem to work if you're inside a tmux session on the remote host. There's probably a way to
get it working, but I've just been doing `git pull` outside of tmux.

Once the tunnel is up, you can go to `http://localhost:8666`, where you'll be asked to sign in. Sign in as
user `protocol` with an empty password.

## Server Environment

There are some things specific to the environment that are worth mentioning.

The testground daemon is running inside a tmux session owned by the `jupyter-protocol` user. Running `tmux attach`
while shelled in should open it for you - you may have to switch to a different pane - it's generally running in
the first pane.

If for some reason testground isn't running, (e.g. `ps aux | grep testground` comes up empty), you can start the
daemon with:

```shell
testground --vv daemon
```

The testground that's on the `$PATH` is a symlink to `~/repos/testground/testground`, so if you pull in changes
to testground and rebuild, it should get picked up by the runner scripts, etc automatically.

This repo is checked out to `~/repos/gossipsub-hardening`, and there's a symlink to it in `~/testground/plans`, so that
the daemon can find it and run our plans.

## Cluster setup

The [testground/infra](https://github.com/testground/infra) repo is checked out at `~/repos/infra`. It contains
the scripts for creating and deleting the k8s cluster. The infra README has more detail and some helpful commands,
but here are some of the most relevant, plus some things to try if things break.

Before running any of the commands related to the cluster, you'll need to source some environment vars:

```
source ~/k8s-env.sh
```


To see the current status of the cluster:

```shell
kops validate cluster
```

If that command can't connect to the cluster VMS at all, it either means the cluster has been deleted, 
or you need to export the kubectl config:

```shell
kops export kubecfg --state $KOPS_STATE_STORE --name=$NAME
```

If `kops validate cluster` still can't connect to anything, someone probably deleted the cluster when they were
done with it. To create it:

```shell
cd ~/repos/infra/k8s
./install.sh cluster.yaml
```

This will take a few minutes, and the newly created cluster will only have 4 workers. To resize it:

```shell
kops edit ig nodes
```

and edit the `maxSize` and `minSize` params - set both to the desired node count. Then, apply the changes with

```shell
kops update cluster $NAME --yes
```

After a few minutes, `kops validate cluster` should show all the instances up, and the cluster will be ready.

## Running Tests

Everything in the [main README](./README.md) should apply when running tests on the server, but you can ignore
the parts that tell you to run `jupyter notebook` manually.

When you log into the Jupyterhub server, you should see a file browser interface. Navigate to 
`repos/gossipsub-hardening/scripts` to open the `Runner.ipynb` notebook.

There are a bunch of `config-*.json` files next to the runner notebook - these are a good starting point for
configuring test variations - the `config-1k.json` is the baseline test described in the report.

At the moment, some of the config json files may still be targeting the `feat/hardening` branch and will give an
error right away if you run them - change the branch in the Pubsub config panel to `master` and it should be all good.

If you want to target "vanilla" gossipsub (v1.0), you can set the branch to `release-v0.2` and uncheck the
"target hardened API" checkbox in the UI.

After a successful run, you should see the path to the analysis notebook printed. Nav there with the Jupyter
file browser to run the analysis notebook and generate the charts, etc.

## Troubleshooting

Sometimes, especially if you're running with lots of instances, `weave` (the thing that manages the k8s data network)
will give up the ghost, and one or more test instances will get stuck and be unable to communicate with the others.

If you never see the `All networks initialized` message in the testground output, or if it takes several minutes to
get to `All networks initialized` after all instances are in the Running state, it's likely that you've hit this issue.

If weave has failed, you may see some weave pods stuck in a "not ready" state if you run

```shell
kubectl validate cluster
```

You can try forcibly removing the stuck weaves, although I can't find the magic commands for that at the moment.
What I've been doing instead is scaling the cluster down to a single worker and then back up, to start with a clean
slate. Scaling down to zero would probably be better, now that I think of it...

If you do hit the weave issue, you can try lowering the # of connections for the attacker, having fewer attackers,
or packing the attacker peers less tightly into their containers by adjusting the number of attacker nodes and
the number of attack peers per container. Spreading the attackers out over more containers may help, but you may
also need to resize the cluster and add more worker VMs. 

If you don't have enough resources, testground will fail you right away and helpfully tell you what the limit it.

You can control the CPU and RAM allocated for each test container by editing `~/testground/.env.toml` and restarting
the testground daemon.

[tljh]: http://tljh.jupyter.org/en/latest/
