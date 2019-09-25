import json
import logging
import os
import subprocess as sp

CMD_SYSTEMCTL_ENABLE = "systemctl enable {}"


class Chroot:
    """
    Context manager for a chroot command:
    with Chroot("/mnt"):
        # Do stuff in /mnt chroot
        ...
    """
    def __init__(self, directory):
        """
        :param directory: Directory to chroot to
        """
        self._directory = directory
        self._work_dir = os.getcwd()
        self._fs_root = None

    def __enter__(self):
        self._fs_root = os.open("/", os.O_RDONLY)
        os.chdir(self._directory)
        os.chroot(self._directory)

    def __exit__(self, exc_type, exc_val, exc_tb):
        os.fchdir(self._fs_root)
        os.chroot(".")
        os.close(self._fs_root)
        os.chdir(self._work_dir)
        self._fs_root = None
        return False


def read_file(path):
    """
    Write contents to path
    :param path: Path to read from
    :return: File contents on success, None on failure
    """
    contents = None

    try:
        logging.info("Reading {}...".format(path))
        with open(path) as f:
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
        with open(path, file_mode) as f:
            f.write(contents)
    except Exception as e:
        logging.warning("Error writing {}: {}".format(path, e))
        return False

    return True


def run_cmd(cmd, return_output=False, chroot=""):
    """
    Runs the given cmd. If return_output, return stdout or None on error.
    Else return a boolean indicating whether the operation was successful
    :param cmd: Command to run
    :param return_output: Whether to return a string or boolean
    :param chroot: Filesystem root for the command
    :return: Stdout or boolean indicating if the operation was
    sucessful
    """

    if chroot != "":
        with Chroot(chroot):
            completed_process = sp.run(
                cmd,
                shell=True,
                stdout=sp.PIPE,
                stderr=sp.PIPE
            )
    else:
        completed_process = sp.run(
            cmd,
            shell=True,
            stdout=sp.PIPE,
            stderr=sp.PIPE
        )

    if not return_output:
        logging.debug(completed_process.stdout.decode("utf-8"))

    if completed_process.returncode != 0:
        logging.error(completed_process.stderr.decode("utf-8"))
        if return_output:
            return None
        return False

    if return_output:
        return completed_process.stdout.decode("utf-8").strip()
    return True


def systemd_enable(service_name, chroot=""):
    command = CMD_SYSTEMCTL_ENABLE.format(service_name)
    if chroot != "":
        with Chroot(chroot):
            success = run_cmd(command)
    else:
        success = run_cmd(command)
    return success


def load_status(status_file):
    """
    Loads the given json status_file
    :param status_file: File to load
    :return: A dict based on the json contents of status_file
    """
    status = read_file(status_file)
    if status is not None:
        return json.loads(status)
    return None


def save_status(status_file, status_dict):
    """
    Save the given status as a json file
    :param status_file: File to load
    :param status_dict: Dict of variabled from the script
    :return: None
    """
    return write_file(status_file, json.dumps(status_dict))


def exit_script(status_code, status_file, status_dict):
    """
    Writes status_array to status_file and returns status_code
    :param status_code: Code to return from this function
    :param status_file: File to write status_array to
    :param status_dict: Status dict for the current run of the script
    :return: status_code
    """
    if save_status(status_file, status_dict):
        return status_code
    return 1
