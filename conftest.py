import os


def pytest_addoption(parser):
    parser.addoption("--reference", action="store_true", default=False,
                     help="swap every exercise for its reference solution (needs reference/)")
    parser.addoption("--fill", action="store_true", default=False,
                     help="use the reference only for exercises you haven't started (needs reference/)")


def pytest_configure(config):
    if config.getoption("--reference"):
        os.environ["NANOSERVE_REFERENCE"] = "1"
    elif config.getoption("--fill"):
        os.environ["NANOSERVE_REFERENCE"] = "auto"
