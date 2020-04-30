# gossipsub-hardening

This repo contains [testground](https://github.com/testground/testground) test plans designed to evaluate the 
performance of gossipsub under various attack scenarios.

## Installation & Setup

We're using python to generate testground composition files, and we shell out to a few 
external commands, so there's some environment setup to do.

If you want to run tests on the Protocol Labs Jupyterhub instance, see 
[README-shared-environment.md](./README-shared-environment.md), then read [Running Tests](#running-tests) below.

### Requirements

#### Testground

You'll need to have the [testground](https://github.com/testground/testground) binary built and accessible
on your `$PATH`. As of the time of writing, we're running from `master`, however releases after v0.5.0 should
be compatible.

After running `testground list` for the first time, you should have a `~/testground` directory. You can change this
to another location by setting the `TESTGROUND_HOME` environment variable.

#### Cloning this repo

The testground client will look for test plans in `$TESTGROUND_HOME/plans`, so this repo should be cloned or
symlinked into there:

```shell
cd ~/testground/plans # if this dir doesn't exist, run 'testground list' once first to create it
git clone git@github.com:protocol/gossipsub-hardening.git
```

#### Python

We need python 3.7 or later, ideally in a virtual environment. If you have python3 installed, you can create
a virtual environment named `venv` in this repo and it will be ignored by git:

```shell
python3 -m venv venv
```

After creating the virtual environment, you need to "activate" it for each shell session:

```shell
# bash / zsh:
source ./venv/bin/activate

# fish:
source ./venv/bin/activate.fish
```

You'll also need to install the python packages used by the scripts:

```shell
pip install -r scripts/requirements.txt
```

#### External binaries

The run scripts rely on a few commands being present on the `PATH`:

- the `testground` binary
- `go`

## Running Tests

### Running using the Runner Jupyter notebook

With the python virtualenv active, run 

```shell
jupyter notebook
```

This will start a Jupyter notebook server and open a browser to the Jupyter file navigator.
In the Jupyter UI, navigate to the `scripts` dir and open `Runner.ipynb`.

This will open the runner notebook, which lets you configure the test parameters using a
configuration UI.

You'll need to run all the cells to prepare the notebook UI using `Cell menu > Run All`. You can reset
the notebook state using the `Kernel Menu > Restart and Run All` command.

The cell at the bottom of the notebook has a "Run Test" button that will convert the configured parameters
to a composition file and start running the test. It will shell out to the `testground` client binary,
so if you get an error about a missing executable, make sure `testground` is on your `PATH` and restart
the Jupyter server.

At the end of a successful test, there will be a new `output/pubsub-test-$timestamp` directory (relative to
the `scripts` dir) containing the composition file, the full `test-output.tgz` file collected from testground,
and an `analysis` directory.

The `analysis` directory has relevant files that were extracted from the `test-output.tgz` archive, along with a
new Jupyter notebook, `Analysis.ipynb`. See below for more details about the analysis notebook.

If the test fails (`testground` returns a non-zero exit code), the runner script will move the `pubsub-test-$timestamp`
dir to `./output/failed`.

The "Test Execution" section of the config UI will let you override the output path, for example if you want
to give your test a meaningful name.

### Targeting a specific version of go-libp2p-pubsub

The default configuration is to test against the current `master` branch of go-libp2p-pubsub,
but you can change that in the `Pubsub` panel of the configuration UI. You can enter the name
of a branch or tag, or the full SHA-1 hash of a specific commit.

**Important:** if you target a version before [the Gossipsub v1.1 PR](https://github.com/libp2p/go-libp2p-pubsub/pull/273)
was merged, you must uncheck the "target hardening branch API" checkbox to avoid build failures due to
missing methods.

#### Saved test configurations

You can save configuration snapshots to JSON files and load them again using the buttons at the bottom
of the configuration panel. The snapshots contain the state of all the configuration widgets, so can
only be used with the Runner notebook, not the command line `run.py` script.

There are several saved configs in `scripts/configs` that we've been using to evaluate different
scenarios. The "baseline" config is `scripts/configs/1k.json`, which sets up a test with 1000 honest
nodes and no attackers.

The saved configs are all setup to use the `cluster:k8s` runner, and they expect to find the testground
daemon on a non-standard port (8080 instead of 8042). If you're using our 
[shared jupyterhub server](./README-shared-environment.md), this should all Just Work, but if you're running
elsewhere you may need to change those parameters to suit your environment.

### Running using the cli scripts

Inside the `scripts` directory, the `run.py` script will generate a composition and run it by shelling out to
`testground`. If you just want it to generate the composition, you can skip the test run by passing the `--dry-run`
flag.

You can get the full usage by running `./run.py --help`.

To run a test with baseline parameters (as defined in `scripts/templates/baseline/params/_base.toml`), run:

```shell
./run.py
```

By default, this will create a directory called `./output/pubsub-test-$timestamp`, which will have a `composition.toml`
file inside, as well as a `template-params.toml` that contains the params used to generate the composition.

You can control the output location with the `-o` and `--name` flags, for example:

```shell
./run.py -o /tmp --name 'foo'
# creates directory at /tmp/pubsub-test-$timestamp-foo
```

Note that the params defined in `scripts/templates/baseline/params/_base.toml` have very low instance counts and
are likely useless for real-world evaluation of gossipsub.

You can override individual template parameters using the `-D` flag, for example, `./run.py -D T_RUN=5m`.
There's no exhaustive list of template parameters, so check the template at `scripts/templates/baseline/template.toml.j2`
to see what's defined.

Alternatively, you can create a new toml file containing the parameters you want to set, and it will override
any parameters defined in `scripts/templates/baseline/params/_base.toml`

By default, the `run.py` script will extract the test data from the collected test output archive and copy the
analysis notebook to the `analysis` subdirectory of the test output dir. If you want to skip this step,
you can pass the `--skip-analysis` flag.

## Analyzing Test Outputs

After running a test, there should be a directory full of test outputs, with an `analysis` dir containing
an `Analysis.ipynb` Jupyter notebook. If you're not already running the Jupyter server, start it with
`jupyter notebook`, and use the Jupyter UI to navigate to the analysis notebook and open it.

Running all the cells in the analysis notebook will convert the extracted test data to 
[pandas](https://pandas.pydata.org/) `DataFrame`s. This conversion takes a minute or two depending on the
size of the test and your hardware, but the results are cached to disk, so future runs should be pretty fast.

Once everything is loaded, you'll see some charts and tables, and there will be a new `figures` directory inside the 
`analysis` dir containing the charts in a few image formats. There's also a `figures.zip` with the same contents
for easier downloading / storage.

### Running the analysis notebook from the command line

If you just want to generate the charts and don't care about interacting with the notebook, you can execute
the analysis notebook using a cli script.

Change to the `scripts` directory, then run

```shell
./analyze.py run_notebook ./output/pubsub-test-$timestamp
```

This will copy the latest analysis notebook template into the `analysis` directory and execute the notebook, which
will generate the chart images. 

This command is useful if you've made changes to the analysis notebook template and want to re-run it against a
bunch of existing test outputs. In that case, you can pass multiple paths to the `run_notebook` subcommand:

 ```shell
 ./analyze.py run_notebook ./output/pubsub-test-*
# will run the latest notebook against everything in `./output
 ```


## Code Overview

The test code all lives in the `test` directory.

`main.go` is the actual entry point, but it just calls into the "real" main function, `RunSimulation`, which is defined
in `run.go`.

`params.go` contains the parameter parsing code. The `parseParams` function will return a `testParams` struct will
all test parameters. Note that some params only apply to specific types of node, for example the `SybilParams` are only
used by attacker nodes, while `OverlayParams` is only used by honest nodes. To simplify the parsing, they're all
included in the `testParams` struct, but each node type will only use what they need. 

The set of params provided to each test instance depends on which composition group they're in. The composition
template we're using defines three groups: `publishers`, `lurkers`, and `attackers`. The attackers have the `sybil`
param set to `true`, while the honest groups have it set to the default of `false`. The lurkers and publishers have
identical params with the exception of the boolean `publisher` param, which controls whether they will publish messages
or just consume them. 

After parsing the params, `RunSimulation` will prepare the libp2p `Host`s, do some network setup and then
call either `runHonest` or `runSybil` for each `Host`, depending on the node type specified in the params. Note that
there may be multiple `Host`s for one test instance, depending on the configuration. We generally run multiple attacker
nodes in a container but run each honest node in its own container. This is because honest nodes require more resources,
and because the artificial network latency does not apply between peers in the same container. Since the sybils never
connect to each other, we don't care about simulating latency between them.

`discovery.go` contains a `SyncDiscovery` component that uses the testground sync service to broadcast information about
the test peers (e.g. addreses, whether they're honest, etc) with every other peer. It uses this information to connect
nodes to each other in various topologies.

The honest node implementation is in `honest.go`, and there are also `honest_hardened.go` and `honest_vanilla.go` files
that allow us to target the new gossipsub v1.1 API or the old "vanilla" API by setting a build tag. If the vanilla API
is used, the test will not produce any peer score information, since that was added in v1.1, however you will see the
effect of the attacks in the latency distribution.

The sybil nodes are implemented in `badboy.go`, which provides a minimal gossipsub implementation with some nasty
behaviors.

The `tracer.go` file implements the `pubsub.EventTracer` interface to capture pubsub events and produce test metrics.
Because the full tracer output is quite large (several GB for a few minutes of test execution with lots of nodes),
we aggregate the trace events at runtime and spit out a json file with aggregated metrics at the end of the test.
We also capture a filtered subset of the original traces, containing only Publish, Deliver, Graft, and Prune events.
At the end of the test, we run [tracestat](https://github.com/libp2p/go-libp2p-pubsub-tracer/blob/master/cmd/tracestat/main.go)
on the filtered traces to calculate the latency distribution and get a summary of publish and deliver counts.