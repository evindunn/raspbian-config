import logging
import subprocess as sp


def run_cmd(cmd, return_output=False):
    """
    Runs the given cmd. If return_output, return stdout or None on error.
    Else return a boolean indicating whether the operation was successful
    :param cmd: Command to run
    :param return_output: Whether to return a string or boolean
    :return: Stdout or boolean indicating if the operation was
    sucessful
    """
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
