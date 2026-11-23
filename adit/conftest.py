import multiprocessing

# The live server of the acceptance tests (ChannelsLiveServer from adit_radis_shared)
# runs Daphne in a child process that has to be forked; Python 3.14 made forkserver
# the default start method on Linux.
multiprocessing.set_start_method("fork", force=True)

pytest_plugins = ["adit_radis_shared.pytest_fixtures"]
