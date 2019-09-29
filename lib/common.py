import logging
import subprocess as sp

CMD_SYSTEMCTL_ENABLE = "systemctl enable {}"


def read_file(path):
    """
    Write contents to path
    :param path: Path to read from
    :return: File contents on success, None on failure
    """
    contents = None

    try:
        logging.info("Reading {}...".format(path))
        with open(path, encoding="utf-8") as f:
            contents = f.read()
    except Exception as e:
        logging.warning("Error reading {}: {}".format(path, e))

    return contents


def write_file(path, contents, append=False):
    """
    Write contents to path
    :param path: Path to write to
    :param contents: Content to write
    :param append: Whether to append the contents to the end of the file
    :return: Whether the operation was successful
    """
    if append:
        file_mode = "a"
    else:
        file_mode = "w"
    try:
        logging.info("Writing {}...".format(path))
        with open(path, file_mode, encoding="utf-8") as f:
            f.write(contents)
    except Exception as e:
        logging.warning("Error writing {}: {}".format(path, e))
        return False

    return True


def run_cmd(cmd, return_output=False):
    """
    Runs the given cmd. If return_output, return stdout or None on error.
    Else return a boolean indicating whether the operation was successful
    :param cmd: Command to run
    :param return_output: Whether to return a string or boolean
    :param chroot: Filesystem root for the command
    :return: Stdout or boolean indicating if the operation was
    sucessful
    """

    try:
        completed_process = sp.run(
            cmd,
            shell=True,
            stdout=sp.PIPE,
            stderr=sp.PIPE
        )
    except Exception as e:
        logging.error("Error running '{}': {}".format(cmd, str(e).strip()))
        if return_output:
            return None
        return False

    if not return_output:
        logging.debug(completed_process.stdout.decode("utf-8").strip())

    if completed_process.returncode != 0:
        logging.error(completed_process.stderr.decode("utf-8").strip())
        if return_output:
            return None
        return False

    if return_output:
        return completed_process.stdout.decode("utf-8").strip()
    return True


def systemd_enable(service_name):
    return run_cmd(CMD_SYSTEMCTL_ENABLE.format(service_name))
