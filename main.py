import os
import logging
import json
from time import time, sleep
from api4jenkins import Jenkins

log_level = os.environ.get('INPUT_LOG_LEVEL', 'INFO')
logging.basicConfig(format='JENKINS_ACTION: %(message)s', level=log_level)

def fetch_env_variables():
    return {
        "url": os.environ["INPUT_URL"],
        "job_name": os.environ["INPUT_JOB_NAME"],
        "username": os.environ.get("INPUT_USERNAME"),
        "api_token": os.environ.get("INPUT_API_TOKEN"),
        "parameters": os.environ.get("INPUT_PARAMETERS"),
        "cookies": os.environ.get("INPUT_COOKIES"),
        "wait": bool(os.environ.get("INPUT_WAIT")),
        "timeout": int(os.environ.get("INPUT_TIMEOUT")),
        "start_timeout": int(os.environ.get("INPUT_START_TIMEOUT")),
        "interval": int(os.environ.get("INPUT_INTERVAL"))
    }

def get_auth(username, api_token):
    if username and api_token:
        return (username, api_token)
    logging.info('Username or token not provided. Connecting without authentication.')
    return None

def parse_json(data, name):
    if data:
        try:
            return json.loads(data)
        except json.JSONDecodeError as e:
            raise Exception(f'`{name}` is not valid JSON.') from e
    return {}

def connect_to_jenkins(url, auth, cookies):
    jenkins = Jenkins(url, auth=auth, cookies=cookies)
    try:
        jenkins.version
    except Exception as e:
        raise Exception('Could not connect to Jenkins.') from e
    logging.info('Successfully connected to Jenkins.')
    return jenkins

def main():
    env_vars = fetch_env_variables()

    auth = get_auth(env_vars["username"], env_vars["api_token"])

    parameters = parse_json(env_vars["parameters"], 'parameters')

    cookies = parse_json(env_vars["cookies"], 'cookies')

    jenkins = connect_to_jenkins(env_vars["url"], auth, cookies)

    queue_item = jenkins.build_job(env_vars["job_name"], **parameters)

    logging.info('Requested to build job.')

    t0 = time()
    sleep(env_vars["interval"])
    while time() - t0 < env_vars["start_timeout"]:
        build = queue_item.get_build()
        if build:
            break
        logging.info(f'Build not started yet. Waiting {env_vars["interval"]} seconds.')
        sleep(env_vars["interval"])
    else:
        raise Exception(
            f"Could not obtain build and timed out. Waited for {env_vars["start_timeout"]} seconds.") # noqa

    build_url = build.url
    logging.info(f"Build URL: {build_url}")
    with open(os.environ['GITHUB_OUTPUT'], 'a') as fh:
      print(f'build_url={build_url}', file=fh)
    print(f"::notice title=build_url::{build_url}")

    if not env_vars["wait"]:
        logging.info("Not waiting for build to finish.")
        return

    t0 = time()
    sleep(env_vars["interval"])
    while time() - t0 < env_vars["timeout"]:
        result = build.result
        if result == 'SUCCESS':
            logging.info('Build successful 🎉')
            return
        elif result in ('FAILURE', 'ABORTED', 'UNSTABLE'):
            raise Exception(
                f'Build status returned "{result}". Build has failed ☹️.')
        logging.info(
            f'Build not finished yet. Waiting {env_vars["interval"]} seconds. {build_url}')
        sleep(env_vars["interval"])
    else:
        raise Exception(
            f"Build has not finished and timed out. Waited for {env_vars["timeout"]} seconds.") # noqa


if __name__ == "__main__":
    main()