# gossipsub-hardening-tests

This repo contains [testground](https://github.com/testground/testground) test plans designed to evaluate the 
performance of gossipsub under various attack scenarios.

## Installation & Setup

We're using python to generate testground composition files, and we shell out to a few 
external commands, so there's some environment setup to do.

### Requirements

#### Testground

You'll need to have the [testground](https://github.com/testground/testground) binary built and accessible
on your `$PATH`. As of the time of writing, we're running from `master`, however releases after v0.5.0 should
be compatible.

After running `testground` for the first time, you should have a `~/testground` directory. You can change this
to another location by setting the `TESTGROUND_HOME` environment variable.

#### Cloning this repo

The testground client will look for test plans in `$TESTGROUND_HOME/plans`, so this repo should be cloned or
symlinked into there:

```shell
cd ~/testground/plans # if this dir doesn't exist, run testground once first to create it
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
- `gnuplot` (optional, you'll just get an error message and no latency svg file)

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

You can save configuration snapshots to JSON files and load them again using the buttons at the bottom
of the configuration panel.

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

You can override individual template parameters using the `-D` flag, for example, `./run.py -D T_RUN=5m`.
There's no exhaustive list of template parameters, so check the template at `scripts/templates/baseline/template.toml.j2`
to see what's defined.

By default, the `run.py` script will extract the test data from the collected test output archive and copy the
analysis notebook to the `analysis` subdirectory of the test output dir. If you want to skip this step,
you can pass the `--skip-analysis` flag.

## Analyzing Test Outputs

After running a test, there should be a directory full of test ouputs, with an `analysis` dir containing
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
